from flask import Flask, render_template, jsonify, request, send_from_directory
import pandas as pd
import os

app = Flask(__name__)

DATA_PATH = os.path.join(os.path.dirname(__file__), 'payer_dataset_2.2.csv')

FILTER_MAP = [
    ('parent_plan',   'parent_plan_name'),
    ('plan_name',     'plan_name'),
    ('drug_name',     'drug_name'),
    ('creator_type',  'creator_user_type'),
    ('revenue_source','revenue_source'),
    ('outcome',       'outcome'),
]


def load_data():
    df = pd.read_csv(DATA_PATH, low_memory=False)

    # Parse datetime columns
    for col in ['epa_ques_req', 'epa_ques_resp', 'epa_pa_req', 'epa_pa_resp', 'ques_set', 'epa_ques_resp_mess']:
        df[col + '_dt'] = pd.to_datetime(df[col], errors='coerce')

    # Compute TAT in seconds
    df['tat12_s'] = (df['epa_ques_resp_dt'] - df['epa_ques_req_dt']).dt.total_seconds()
    df['tat34_s'] = (df['epa_pa_resp_dt']   - df['epa_pa_req_dt']).dt.total_seconds()

    # Fill string columns
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].fillna('Unknown')
    df['outcome'] = df['outcome'].replace('Unknown', 'N/A')

    # Daily date from actual request datetime
    df['pa_date'] = df['epa_ques_req_dt'].dt.strftime('%Y-%m-%d').fillna('Unknown')

    return df


df = load_data()

DATES = sorted(d for d in df['pa_date'].unique().tolist() if d != 'Unknown')


def apply_filters(args):
    mask = pd.Series(True, index=df.index)
    for param, col in FILTER_MAP:
        vals = args.getlist(param)
        if vals:
            mask &= df[col].isin(vals)
    date_from = args.get('date_from')
    date_to   = args.get('date_to')
    if date_from:
        mask &= df['pa_date'] >= date_from
    if date_to:
        mask &= df['pa_date'] <= date_to
    return df[mask]


def fmt(n):
    n = float(n)
    if n >= 1_000_000:
        return f'{n / 1_000_000:.1f}M'
    if n >= 1_000:
        return f'{n / 1_000:.1f}K'
    return f'{int(n):,}'


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/logo')
def logo():
    return send_from_directory(os.path.dirname(__file__), 'CoverMyMeds_Logo.png')


@app.route('/api/filters')
def get_filters():
    result = {}
    for param, col in FILTER_MAP:
        if col in df.columns:
            vals = sorted(
                df[col].replace('Unknown', pd.NA).dropna().astype(str).unique().tolist(),
                key=lambda x: x.lower()
            )
            result[param] = vals
    result['date_min'] = DATES[0]  if DATES else ''
    result['date_max'] = DATES[-1] if DATES else ''
    return jsonify(result)


def _week_stats(wdf):
    step1 = int(wdf['epa_ques_req_dt'].notna().sum())
    step2 = int(wdf['epa_ques_resp_dt'].notna().sum())
    qs    = int(wdf['ques_set_dt'].notna().sum())
    msg   = int(wdf['epa_ques_resp_mess_dt'].notna().sum())
    step3 = int(wdf['epa_pa_req_dt'].notna().sum())
    step4 = int(wdf['epa_pa_resp_dt'].notna().sum())

    tat12_s = wdf['tat12_s']
    tat12 = float(tat12_s[tat12_s > 0].mean()) if (tat12_s > 0).any() else 0

    tat34_s = wdf['tat34_s']
    tat34 = float(tat34_s[tat34_s > 0].mean()) if (tat34_s > 0).any() else 0

    approved = int((wdf['outcome'] == 'Approved').sum())
    denied   = int((wdf['outcome'] == 'Denied').sum())
    fast_mask = (tat34_s > 0) & (tat34_s < 30) & (wdf['outcome'] == 'Approved')
    auto_approvals = int(fast_mask.sum())
    auto_rate = round(100 * auto_approvals / approved, 1) if approved > 0 else 0

    return {
        'step1':          step1,
        'step2':          step2,
        'tat12':          round(tat12, 1),
        'ques_sets':      qs,
        'messaging':      msg,
        'step3':          step3,
        'step4':          step4,
        'tat34':          round(tat34, 1),
        'approvals':      approved,
        'auto_approvals': auto_approvals,
        'auto_rate':      auto_rate,
        'denials':        denied,
    }


@app.route('/api/data')
def get_data():
    filtered = apply_filters(request.args)

    # Waterfall totals
    step1 = int(filtered['epa_ques_req_dt'].notna().sum())
    step2 = int(filtered['epa_ques_resp_dt'].notna().sum())
    qs    = int(filtered['ques_set_dt'].notna().sum())
    msg   = int(filtered['epa_ques_resp_mess_dt'].notna().sum())
    step3 = int(filtered['epa_pa_req_dt'].notna().sum())
    step4 = int(filtered['epa_pa_resp_dt'].notna().sum())

    tat12_s   = filtered['tat12_s']
    tat12_avg = float(tat12_s[tat12_s > 0].mean()) if (tat12_s > 0).any() else 0

    tat34_s   = filtered['tat34_s']
    tat34_avg = float(tat34_s[tat34_s > 0].mean()) if (tat34_s > 0).any() else 0

    # Creator Type
    ct = filtered['creator_user_type'].replace('Unknown', pd.NA).dropna().value_counts()
    ct_total = int(ct.sum())
    creator = [
        {'label': str(k), 'count': int(v), 'pct': round(100 * v / ct_total, 2) if ct_total else 0}
        for k, v in ct.items()
    ]

    # Messaging (reason codes)
    rc = filtered['reason_code'].replace('Unknown', pd.NA).dropna().value_counts().head(10)
    messaging = [{'code': str(k), 'count': int(v)} for k, v in rc.items()]

    # Outcome
    oc = filtered['outcome'].value_counts()
    oc_total = int(oc.sum())
    outcome = [
        {'label': str(k), 'count': int(v), 'pct': round(100 * v / oc_total, 2) if oc_total else 0}
        for k, v in oc.items()
    ]

    # Totals
    total_rows     = len(filtered)
    total_approved = int((filtered['outcome'] == 'Approved').sum())
    total_denied   = int((filtered['outcome'] == 'Denied').sum())

    # Waterfall Detail table (daily)
    dates = sorted(d for d in filtered['pa_date'].unique().tolist() if d != 'Unknown')
    detail = []
    for dt in dates:
        row = _week_stats(filtered[filtered['pa_date'] == dt])
        row['date'] = dt
        detail.append(row)

    return jsonify({
        'waterfall': {
            'step1':     step1,
            'step2':     step2,
            'ques_sets': qs,
            'messaging': msg,
            'step3':     step3,
            'step4':     step4,
            'tat12_avg': round(tat12_avg, 1),
            'tat34_avg': round(tat34_avg, 1),
            'labels': [
                fmt(step1), fmt(step2), fmt(qs), fmt(msg), fmt(step3), fmt(step4)
            ],
        },
        'creator':   creator,
        'messaging': messaging,
        'outcome':   outcome,
        'totals': {
            'total':    fmt(total_rows),
            'approved': fmt(total_approved),
            'denied':   fmt(total_denied),
        },
        'detail': detail,
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(debug=False, host='0.0.0.0', port=port)
