
import streamlit as st
import pandas as pd, joblib, numpy as np, shap
st.set_page_config(layout='wide', page_title='Churn Explainer (Custom)')

st.title('Churn Explainer — Custom Demo')

# Load artifacts
art = joblib.load('/mnt/data/artifacts_for_streamlit.pkl')
preproc = art['preproc']
lgb_model = art['lgb_model']
gb_model = art['gb_model']
feature_names = art['feature_names']

@st.cache_data
def load_data():
    return pd.read_csv(r"/mnt/data/autoinsurance_churn (1).csv")

df = load_data()
# Prepare working df (same logic minimal)
if 'customer_id' not in df.columns:
    df['customer_id'] = ['C{:06d}'.format(i) for i in range(len(df))]
st.sidebar.header('Select customer')
cust = st.sidebar.selectbox('Customer', df['customer_id'].tolist())

row = df[df['customer_id']==cust].reset_index(drop=True)
st.subheader('Customer snapshot')
st.table(row.T)

# Predict with LightGBM and GB
try:
    Xrow = row[[c for c in ['age','tenure_months','premium_amount','claims_count','days_since_last_claim','satisfaction_score','auto_debit','gender','income_bracket','region','payment_frequency'] if c in row.columns]]
    prob_l = lgb_model.predict_proba(preproc.transform(Xrow))[:,1][0]
    prob_g = gb_model.predict_proba(preproc.transform(Xrow))[:,1][0]
    st.metric('LightGBM churn prob', f\"{prob_l:.2f}\", delta=None)
    st.metric('GradientBoost churn prob', f\"{prob_g:.2f}\", delta=None)
except Exception as e:
    st.write('Prediction failed:', e)

# SHAP explanation (LightGBM)
st.subheader('SHAP top contributors (LightGBM)')
expl = shap.TreeExplainer(lgb_model)
try:
    Xp = preproc.transform(Xrow)
    sv = expl.shap_values(Xp)
    if isinstance(sv, list) and len(sv)>1:
        sv_pos = sv[1][0]
    else:
        sv_pos = sv[0][0]
    # prepare df
    shap_df = pd.DataFrame({'feature': feature_names, 'shap': sv_pos})
    shap_df = shap_df.reindex(shap_df['shap'].abs().sort_values(ascending=False).index).head(8)
    st.table(shap_df)
except Exception as e:
    st.write('SHAP failed:', e)

# Human-like summary (reuse rules)
st.subheader('Human-friendly summary')
from math import isfinite
def generate_summary(row):
    try:
        Xr = row[[c for c in ['age','tenure_months','premium_amount','claims_count','days_since_last_claim','satisfaction_score','auto_debit','gender','income_bracket','region','payment_frequency'] if c in row.columns]]
        prob = lgb_model.predict_proba(preproc.transform(Xr))[:,1][0]
        expl = shap.TreeExplainer(lgb_model)
        Xp = preproc.transform(Xr)
        sv = expl.shap_values(Xp)
        svp = sv[1][0] if isinstance(sv, list) and len(sv)>1 else sv[0][0]
        feats = list(zip(feature_names, svp))
        feats_sorted = sorted(feats, key=lambda x: abs(x[1]), reverse=True)[:3]
        headline = f"Predicted churn probability: {prob:.2f} - {'HIGH' if prob>0.5 else 'MEDIUM' if prob>0.25 else 'LOW'}"
        bullets = [f"{f}: {'increases' if v>0 else 'reduces'} risk (contrib {v:.3f})" for f,v in feats_sorted]
        # what-if premium 10%
        what_if = ''
        if 'premium_amount' in Xr.columns:
            mod = Xr.copy()
            mod['premium_amount'] = mod['premium_amount'] * 0.9
            newp = lgb_model.predict_proba(preproc.transform(mod))[:,1][0]
            what_if = f'If premium reduced by 10%, churn prob falls from {prob:.2f} -> {newp:.2f}.'
        return headline, bullets, what_if
    except Exception as e:
        return 'error', [str(e)], ''

headline, bullets, what_if = generate_summary(row)
st.write(headline)
for b in bullets:
    st.write('-', b)
st.write(what_if)
