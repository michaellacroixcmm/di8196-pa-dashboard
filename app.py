from flask import Flask, render_template, jsonify, request, send_from_directory
import pandas as pd
import os

app = Flask(__name__)

@app.route('/logo')
def logo():
    return send_from_directory(os.path.dirname(__file__), 'CoverMyMeds_Logo.png')

DATA_PATH = os.path.join(os.path.dirname(__file__), 'test_platform_dataset_size_example_v5.csv')

NUMERIC_COLS = [
    'request_id_count', 'accessed_online', 'sent_to_plan', 'approved',
    'gross_revenue', 'sum_of_real_pas', 'sum_of_epas', 'sum_of_sponsored',
    'denied', 'faxed_phys',
]

FILTER_MAP = [
    ('account',         'account_name'),
    ('api_client',      'api_client'),
    ('revenue_source',  'revenue_source'),
    ('pa_start_type',   'pa_start_type'),
    ('is_sponsored',    'pa_sponsored_experience_flag'),
    ('is_real',         'real'),
    ('is_epa',          'is_epa'),
    ('reject_code',     'reject_code_clean'),
    ('rejection_code',  'rejection_code'),
    ('state',           'state'),
    ('lob',             'line_of_business'),
    ('drug_name',       'drug_name'),
    ('drug_group',      'drug_group'),
    ('plan_name',       'plan_name'),
    ('generic_flag',    'Generic_DDID_Flag'),
    ('multisource',     'multisource'),
    ('otc',             'otc_flag'),
]

BREAKOUT_COLS = {
    'is_epa':         'is_epa',
    'is_sponsored':   'sponsored',
    'is_real':        'real',
    'state':          'state',
    'revenue_source': 'revenue_source',
    'pa_start_type':  'pa_start_type',
    'reject_code':    'reject_code_clean',
    'account':        'account_name',
    'plan_name':      'plan_name',
    'drug_name':      'drug_name',
}


def load_data():
    data = pd.read_csv(DATA_PATH)
    data['created_month'] = pd.to_datetime(data['created_month'])
    for col in NUMERIC_COLS:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
    for col in data.select_dtypes(include=['object']).columns:
        data[col] = data[col].fillna('Unknown')
    return data


df = load_data()


def apply_filters(data, args):
    for param, col in FILTER_MAP:
        vals = args.getlist(param)
        if vals:
            data = data[data[col].isin(vals)]
    date_from = args.get('date_from')
    date_to   = args.get('date_to')
    if date_from:
        data = data[data['created_month'] >= pd.Timestamp(date_from)]
    if date_to:
        data = data[data['created_month'] <= pd.Timestamp(date_to)]
    return data


def fmt(n):
    n = float(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{int(n):,}"


def fmt_currency(n):
    return '$' + fmt(n)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/filters')
def get_filters():
    result = {}
    for param, col in FILTER_MAP:
        if col in df.columns:
            vals = sorted(
                df[col].dropna().astype(str).unique().tolist(),
                key=lambda x: x.lower()
            )
            result[param] = vals
    months = sorted(df['created_month'].unique())
    result['months'] = [pd.Timestamp(m).strftime('%Y-%m-%d') for m in months]
    return jsonify(result)


@app.route('/api/data')
def get_data():
    filtered = apply_filters(df.copy(), request.args)
    breakout = request.args.get('breakout', 'total')

    total_pas = filtered['request_id_count'].sum()
    total_rev = filtered['gross_revenue'].sum()
    ipa_vol = filtered[filtered['real'] == 'Real']['request_id_count'].sum()
    accessed = filtered['accessed_online'].sum()
    sent = filtered['sent_to_plan'].sum()
    approved = filtered['approved'].sum()

    phy_rate = (accessed / total_pas * 100) if total_pas else 0
    snt_rate = (sent / total_pas * 100) if total_pas else 0
    apr_rate = (approved / total_pas * 100) if total_pas else 0

    months = sorted(filtered['created_month'].unique())
    month_labels = [pd.Timestamp(m).strftime('%b %Y') for m in months]

    total_series = None
    if breakout == 'total' or breakout not in BREAKOUT_COLS:
        monthly = filtered.groupby('created_month')['request_id_count'].sum()
        datasets = [{
            'label': 'Total',
            'data': [int(monthly.get(m, 0)) for m in months],
            'backgroundColor': '#ff8f1c',
        }]
        table_rows = [['Total'] + [f"{int(monthly.get(m, 0)):,}" for m in months]]
    else:
        col = BREAKOUT_COLS[breakout]

        # All unique values and their totals — used for top-N filtering
        val_totals = (
            filtered.groupby(col)['request_id_count'].sum()
            .sort_values(ascending=False)
        )
        total_series = len(val_totals)

        top_n_raw = request.args.get('top_n', '')
        if top_n_raw.isdigit() and int(top_n_raw) > 0:
            bk_vals = val_totals.head(int(top_n_raw)).index.tolist()
        else:
            bk_vals = val_totals.index.tolist()

        # Sort largest-first so Chart.js stacks them largest at bottom
        grp = filtered.groupby(['created_month', col])['request_id_count'].sum()
        datasets = []
        table_rows = []
        for val in bk_vals:
            data_pts = [int(grp.get((m, val), 0)) for m in months]
            datasets.append({'label': str(val), 'data': data_pts})
            table_rows.append([str(val)] + [f"{v:,}" for v in data_pts])

    acct_sel = request.args.getlist('account')
    client_sel = request.args.getlist('api_client')
    reject_sel = request.args.getlist('reject_code')

    return jsonify({
        'kpis': {
            'total_pa':       fmt(total_pas),
            'total_revenue':  fmt_currency(total_rev),
            'ipa_volume':     fmt(ipa_vol),
            'physician_rate': f"{phy_rate:.1f}%",
            'physician_num':  fmt(accessed),
            'sent_rate':      f"{snt_rate:.1f}%",
            'sent_num':       fmt(sent),
            'approval_rate':  f"{apr_rate:.1f}%",
            'approval_num':   fmt(approved),
            'total_pas_raw':  int(total_pas),
        },
        'selected': {
            'account':     ', '.join(acct_sel)   if acct_sel   else 'All',
            'api_client':  ', '.join(client_sel) if client_sel else 'All',
            'reject_code': ', '.join(reject_sel) if reject_sel else 'All',
        },
        'chart': {
            'labels':   month_labels,
            'datasets': datasets,
        },
        'table': {
            'headers': ['Breakout'] + month_labels,
            'rows':    table_rows,
        },
        'total_series': total_series,
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)
