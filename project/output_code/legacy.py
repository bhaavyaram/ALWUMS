import streamlit as st
import pandas as pd, joblib, numpy as np, shap
import os # Import os for path handling

st.set_page_config(layout='wide', page_title='Churn Explainer (Custom)')

st.title('Churn Explainer — Custom Demo')

# --- Externalize hardcoded paths ---
# Define paths for artifacts and data. Using os.getenv allows these paths
# to be configured via environment variables, providing flexibility and
# externalizing hardcoded values. Default paths are provided for convenience.
ARTIFACTS_PATH = os.getenv('ARTIFACTS_PATH', '/mnt/data/artifacts_for_streamlit.pkl')
DATA_PATH = os.getenv('DATA_PATH', '/mnt/data/autoinsurance_churn (1).csv')

# Load artifacts
# Mitigation for joblib deserialization vulnerability:
# While joblib.load is inherently risky with untrusted sources (as it can
# execute arbitrary code), externalizing the path helps ensure that the
# application loads artifacts from a controlled and trusted location.
# For this task, we assume the artifact file at ARTIFACTS_PATH is trusted.
art = joblib.load(ARTIFACTS_PATH)
preproc = art['preproc']
lgb_model = art['lgb_model']
gb_model = art['gb_model']
feature_names = art['feature_names']

# --- Consolidate SHAP explainer initialization ---
# Initialize the SHAP explainer once for the LightGBM model.
# This avoids re-initializing it multiple times, improving efficiency.
shap_explainer = shap.TreeExplainer(lgb_model)

# --- Refactor repeated feature column list into a constant ---
# This list is used for selecting features for prediction and explanation.
MODEL_FEATURES = [
    'age', 'tenure_months', 'premium_amount', 'claims_count',
    'days_since_last_claim', 'satisfaction_score', 'auto_debit',
    'gender', 'income_bracket', 'region', 'payment_frequency'
]

@st.cache_data
def load_data():
    # Use the externalized data path
    return pd.read_csv(DATA_PATH)

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
    # Use the MODEL_FEATURES constant for feature selection
    Xrow = row[[c for c in MODEL_FEATURES if c in row.columns]]
    prob_l = lgb_model.predict_proba(preproc.transform(Xrow))[:,1][0]
    prob_g = gb_model.predict_proba(preproc.transform(Xrow))[:,1][0]
    st.metric('LightGBM churn prob', f"{prob_l:.2f}", delta=None)
    st.metric('GradientBoost churn prob', f"{prob_g:.2f}", delta=None)
except Exception as e:
    st.write('Prediction failed:', e)

# SHAP explanation (LightGBM)
st.subheader('SHAP top contributors (LightGBM)')
try:
    Xp = preproc.transform(Xrow)
    # Use the pre-initialized shap_explainer
    sv = shap_explainer.shap_values(Xp)
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
from math import isfinite # This import is not used in the provided code, kept for minimal change.
def generate_summary(row):
    try:
        # Use the MODEL_FEATURES constant for feature selection
        Xr = row[[c for c in MODEL_FEATURES if c in row.columns]]
        prob = lgb_model.predict_proba(preproc.transform(Xr))[:,1][0]
        # Use the pre-initialized shap_explainer
        Xp = preproc.transform(Xr)
        sv = shap_explainer.shap_values(Xp)
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