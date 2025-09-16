import streamlit as st
import pandas as pd
import plotly.express as px
import os, datetime, shutil
import uuid

# Optional: pip install pdfkit, smtplib for email
try:
    import pdfkit
    PDFKIT = True
except ImportError:
    PDFKIT = False

import smtplib
from email.message import EmailMessage

st.set_page_config(page_title="Αξιολόγηση Οφειλετών", layout="wide")

# --- Define weights per industry defaults
DEFAULT_WEIGHTS = {
    'Βιομηχανία': {"rating":2, "liquidity":2, "debt_equity":1, "profit":1, "year":1},
    'Εμπόριο':    {"rating":1, "liquidity":1.5, "debt_equity":1, "profit":1, "year":0.5},
    'Υπηρεσίες':  {"rating":1.5, "liquidity":2, "debt_equity":1, "profit":0.5, "year":1},
}
if "weights" not in st.session_state:
    st.session_state["weights"] = DEFAULT_WEIGHTS.copy()

# --- File Paths
DATA_FILE = "ofeiletes_history.csv"
AUDIT_FILE = "audit_trail.csv"
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Helper functions
def log_action(user, action, debtor, details=""):
    now = datetime.datetime.now().isoformat()
    line = pd.DataFrame([[now,user,action,debtor,details]],columns=["timestamp","user","action","debtor","details"])
    if os.path.exists(AUDIT_FILE):
        line.to_csv(AUDIT_FILE,mode='a',header=False,index=False)
    else:
        line.to_csv(AUDIT_FILE,mode='w',header=True,index=False)

def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame()

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def send_email_alert(receiver_email, subject, message):
    # SETTINGS: Put your real SMTP credentials here for production
    EMAIL_ADDRESS = "demo@example.com"
    EMAIL_PASSWORD = "yourpassword"
    SMTP_SERVER = "smtp.example.com"
    SMTP_PORT = 587
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = receiver_email
        msg.set_content(message)
        # Uncomment for real send:
        # with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        #     server.starttls()
        #     server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        #     server.send_message(msg)
        st.success(f"Email προς {receiver_email}: {subject} (demo μόνο – δεν εστάλη email στην έκδοση αυτή)") 
    except Exception as e:
        st.error(f"Πρόβλημα με αποστολή email! {str(e)}")

def generate_pdf(summary_html, filename="debt_report.pdf"):
    if PDFKIT:
        pdfkit.from_string(summary_html, filename)
        return True
    else:
        st.warning("Το pdfkit δεν έχει εγκατασταθεί. Χρησιμοποίησε pip install pdfkit και κατέβασε το wkhtmltopdf!")
        return False

# --- Auth/simple login (for demo: no real user accounts)
if "username" not in st.session_state:
    st.session_state["username"] = st.text_input("Όνομα χρήστη (π.χ. admin, officer):", "admin", key="user")

st.sidebar.title("⚙️ Admin Panel")
is_admin = st.sidebar.checkbox("Λειτουργία Διαχειριστή", value=(st.session_state["username"].lower()=='admin'))

# --- Dynamic weights per κλάδο - μόνο admin
if is_admin:
    st.sidebar.markdown("**Ρύθμιση βαρών αξιολόγησης (ανά κλάδο):**")
    for ind in st.session_state["weights"]:
        for field in st.session_state["weights"][ind]:
            val = st.sidebar.number_input(
                f"{ind} - {field}", min_value=0.0,max_value=5.0,
                value=st.session_state["weights"][ind][field],step=0.1,
                key=f"{ind}_{field}"
            )
            st.session_state["weights"][ind][field] = val

# --- Debtor Form (Insert/Edit)
def debtor_form(edit_data=None):
    st.header("📝 Εισαγωγή / Επεξεργασία Οφειλέτη")
    if edit_data is None:
        edit_data = {}
    name = st.text_input("Όνομα Οφειλέτη", value=edit_data.get("name",""))
    icap = st.number_input("ICAP Rating", 0, 5, int(edit_data.get("icap",3)))
    year = st.number_input("Έτος Ίδρυσης", 1900, 2030, int(edit_data.get("year",2010)))
    employees = st.number_input("Αριθμός Υπαλλήλων", 0, 99999, int(edit_data.get("employees",10)))
    industry = st.selectbox("Κλάδος", list(st.session_state["weights"].keys()), index=0)
    sales = st.number_input("Πωλήσεις", 0.0, None, float(edit_data.get("sales",100000)))
    profit = st.number_input("Κέρδη προ Φόρων", -1e6, 1e6, float(edit_data.get("profit", 20000)))
    margin = st.number_input("Περιθώριο Μικτού Κέρδους %", 0.0, 100.0, float(edit_data.get("margin",30)))
    cash = st.number_input("Ταμειακά Διαθέσιμα", 0.0, None, float(edit_data.get("cash", 15000)))
    liquidity = st.number_input("Liquidity Ratio", 0.0, 10.0, float(edit_data.get("liquidity",1.5)))
    netdebt = st.number_input("Net Debt / Equity", 0.0, 10.0, float(edit_data.get("netdebt",1.0)))
    rec_sales = st.number_input("Εμπορικές Απαιτήσεις / Πωλήσεις %", 0.0, 100.0, float(edit_data.get("rec_sales",20)))
    pay_cost = st.number_input("Εμπορικές Υποχρεώσεις / Κόστος Πωλήσεων %", 0.0, 100.0, float(edit_data.get("pay_cost",30)))
    limits = st.number_input("Αριθμός Υφιστάμενων Ορίων", 0, 50, int(edit_data.get("limits",2)))
    request = st.number_input("Αίτηση (ποσό)", 0.0, None, float(edit_data.get("request", 50000)))
    balance = st.number_input("Εμπορικό Υπόλοιπο", 0.0, None, float(edit_data.get("balance", 60000)))
    reviewer_comment = st.text_area("Σχόλια Reviewer", value=edit_data.get("reviewer_comment",""))
    attachment = st.file_uploader("Ανέβασμα δικαιολογητικού (πχ isologismos.pdf)", type=["pdf","doc","docx"])
    if attachment is not None and name:
        save_path = f"{UPLOAD_DIR}/{name.replace(' ','_')}/"
        os.makedirs(save_path, exist_ok=True)
        with open(f"{save_path}{attachment.name}", 'wb') as f:
            f.write(attachment.read())
        st.info(f"Αρχείο αποθηκεύτηκε: {save_path}{attachment.name}")
    data = dict(
        name=name, icap=icap, year=year, employees=employees, industry=industry,
        sales=sales, profit=profit, margin=margin, cash=cash,
        liquidity=liquidity, netdebt=netdebt,
        rec_sales=rec_sales, pay_cost=pay_cost,
        limits=limits, request=request, balance=balance,
        reviewer_comment=reviewer_comment,
        date=datetime.datetime.now().isoformat()
    )
    return data

def calc_score(d, weights):
    s_rating = weights["rating"] * float(d["icap"])
    s_liquidity = weights["liquidity"] * (2 if float(d["liquidity"])>=1.5 else 1 if float(d["liquidity"])>=1 else 0)
    s_debt = weights["debt_equity"] * (2 if float(d["netdebt"])<1 else 1 if float(d["netdebt"])<=2 else 0)
    s_profit = weights["profit"] * (1 if float(d["profit"])>0 else 0)
    s_year = weights["year"] * (1 if int(d["year"])<=2000 else 0)
    breakdown = {
        "ICAP": s_rating, 
        "Liquidity": s_liquidity,
        "NetDebt/Equity": s_debt,
        "Profit": s_profit,
        "Year": s_year
    }
    score = round(s_rating+s_liquidity+s_debt+s_profit+s_year,2)
    return score, breakdown

def sl_pct(score):
    if score >= 5: return 0.8
    if score >= 3: return 0.6
    if score >= 1: return 0.4
    if score == 0: return 0.3
    if score >= -2: return 0.2
    return 0.1

def decision(request, sl_amt, rl_amt):
    if request <= sl_amt:
        return "Εγκρίνεται"
    elif request <= rl_amt:
        return f"Μερική έγκριση έως {rl_amt:,.0f} €"
    else:
        return "Απόρριψη"

def compare_with_previous(df, new_entry):
    if df.empty: return ""
    prev = df[df.name==new_entry["name"]].sort_values(by="date",ascending=False)
    if prev.empty: return ""
    prev_row = prev.iloc[0]
    diffs = []
    for field in ["profit","liquidity","netdebt","icap"]:
        old = prev_row[field]
        new = new_entry[field]
        if float(old)!=float(new):
            diffs.append(f"{field}: {old} → {new}")
    return "; ".join(diffs)

# --- Main UI
st.title("Αξιολόγηση Οφειλετών (Πλήρης Έκδοση)")
df = load_data()

# ------ CRUD -----
edit_index = None
action_on = st.sidebar.text_input("Όνομα προς Επεξεργασία/Διαγραφή", "")
if action_on:
    matched = df[df["name"]==action_on]
    if not matched.empty:
        st.sidebar.info("Βρέθηκε εγγραφή!")
        if st.sidebar.button("Διαγραφή εγγραφής"):
            df = df[df["name"]!=action_on]
            save_data(df)
            log_action(st.session_state["username"], "delete", action_on, f"Διαγραφή")
            st.sidebar.success("Διαγράφηκε!")
        if st.sidebar.button("Επεξεργασία εγγραφής"):
            edit_index = matched.index[0]
else:
    st.sidebar.info("Υποδεικνύει την εγγραφή που θέλεις να αλλάξεις ή να διαγράψεις.")

if edit_index is not None:
    edit_data = df.iloc[edit_index].to_dict()
    data = debtor_form(edit_data)
    is_edit = True
else:
    data = debtor_form()
    is_edit = False

weights = st.session_state["weights"][data['industry']]
score, breakdown = calc_score(data, weights)
sl = sl_pct(score)
sl_amt = sl * float(data['balance'])
rl_amt = sl_amt*2 if score>=3 else sl_amt*1.5
apofasi = decision(float(data['request']), sl_amt, rl_amt)

# -- Show Results & Visual Feedback
st.subheader("Αποτελέσματα")
cols = st.columns(2)
with cols[0]:
    st.markdown(f"**Score:** {score}")
    st.markdown(f"**SL %:** {sl:.2f}")
    st.markdown(f"**SL ποσό:** {sl_amt:,.0f} €")
    st.markdown(f"**RL ποσό:** {rl_amt:,.0f} €")
    st.markdown(f"**Απόφαση:** <span style='color:{'green' if apofasi=='Εγκρίνεται' else 'orange' if 'Μερική' in apofasi else 'red'}'>{apofasi}</span>", unsafe_allow_html=True)
with cols[1]:
    fig = px.bar(
        x=list(breakdown.keys()), y=list(breakdown.values()), labels={"x":"Παράμετρος", "y":"Score"}, color=list(breakdown.values()),
        title="Ανάλυση υπο-δεικτών"
    )
    st.plotly_chart(fig, use_container_width=True)

st.write("**Σύγκριση με προηγούμενες αξιολογήσεις:**")
diff = compare_with_previous(df,data)
st.info(diff if diff else "Δεν βρέθηκε προηγούμενη αξιολόγηση.")

# -- Sensitivity Analysis
st.subheader("Sensitivity Analysis")
c1,c2,c3 = st.columns(3)
with c1:
    sliquidity = st.slider('Liquidity Ratio', 0.0, 3.0, float(data['liquidity']), 0.1)
with c2:
    snetdebt = st.slider('Net Debt / Equity', 0.0, 3.0, float(data['netdebt']), 0.1)
with c3:
    sprofit = st.slider('Κέρδη προ Φόρων', -100000.0, 200000.0, float(data['profit']), 1000.0)
sscore, sbreak = calc_score(
    {**data,"liquidity":sliquidity,"netdebt":snetdebt,"profit":sprofit}, weights)
ssl = sl_pct(sscore)
ssl_amt = ssl * float(data['balance'])
srl_amt = ssl_amt*2 if sscore>=3 else ssl_amt*1.5
sapofasi = decision(float(data['request']), ssl_amt, srl_amt)
st.write("**[Dynamic] Score:**", sscore)
st.write("**[Dynamic] Απόφαση:**", sapofasi)
st.plotly_chart(
    px.bar(x=list(sbreak.keys()), y=list(sbreak.values()), labels={"x":"Παράμετρος", "y":"Score"}, color=list(sbreak.values()), title="Sensitivity Breakdown"),
    use_container_width=True
)

# -- PDF Export
if PDFKIT:
    if st.button("⬇️ Εξαγωγή αποτελεσμάτων σε PDF"):
        html_rep = f"""
        <h2>Αξιολόγηση Οφειλέτη: {data['name']}</h2>
        <ul>
        <li>Score: {score}</li>
        <li>SL %: {sl}</li>
        <li>SL Ποσό: {sl_amt:,.0f} €</li>
        <li>RL Ποσό: {rl_amt:,.0f} €</li>
        <li>Απόφαση: {apofasi}</li>
        </ul>
        <h4>Breakdown: {breakdown}</h4>
        <h4>Σχόλια: {data.get('reviewer_comment','')}</h4>
        <h4>Υποβλήθηκε: {data['date']}</h4>
        """
        fname = f"{UPLOAD_DIR}/report_{data['name']}_{str(uuid.uuid4())[:4]}.pdf"
        if generate_pdf(html_rep, fname):
            with open(fname, "rb") as f:
                st.download_button("Κατέβασε PDF", f, file_name=os.path.basename(fname))
else:
    st.info("Για PDF Export εγκατέστησε το pdfkit και wkhtmltopdf (δες τεκμηρίωση πάνω)")

# -- Email Notification
if st.button("📧 Στείλε ειδοποίηση (Alert)"):
    send_email_alert("receiver@example.com", f"Αποτέλεσμα για {data['name']}", f"Score: {score}, Απόφαση: {apofasi}")

# Submit to history (CREATE/EDIT)
if st.button("✅ Καταχώριση αξιολόγησης"):
    rec = {**data, **{
        "score":score, "sl_pct":sl, "sl_amt":sl_amt, "rl_amt":rl_amt, "apofasi":apofasi
    }}
    if is_edit and edit_index is not None:
        df.loc[edit_index] = rec
        log_action(st.session_state["username"], "edit", data['name'], "Επεξεργασία εγγραφής")
    else:
        df = pd.concat([df, pd.DataFrame([rec])], ignore_index=True)
        log_action(st.session_state["username"], "insert", data['name'], "Νέα εγγραφή")
    save_data(df)
    st.success("Η εγγραφή αποθηκεύτηκε/ενημερώθηκε!")

# -- View full historic table, filters, KPIs
st.subheader("📚 Ιστορικό αξιολογήσεων & KPIs")
if df.empty:
    st.info("Δεν υπάρχουν καταχωρήσεις.")
else:
    f1, f2 = st.columns(2)
    with f1:
        industry_filter = st.multiselect("Φίλτρο κλάδων", options=df.industry.unique().tolist())
        apofasi_filter = st.multiselect("Φίλτρο απόφασης", options=df.apofasi.unique().tolist())
    with f2:
        year_filter = st.multiselect("Φίλτρο έτους", options=sorted(df.year.unique()))
        user_filter = st.multiselect("Χρήστης/Reviewer", options=df.get("user",["admin"]).unique())
    filtered = df.copy()
    if industry_filter: filtered = filtered[filtered['industry'].isin(industry_filter)]
    if apofasi_filter: filtered = filtered[filtered['apofasi'].isin(apofasi_filter)]
    if year_filter: filtered = filtered[filtered['year'].isin(year_filter)]
    if user_filter and "user" in filtered: filtered = filtered[filtered['user'].isin(user_filter)]
    st.dataframe(filtered)
    st.plotly_chart(px.pie(filtered, names="apofasi", title="Πίτα εγκρίσεων/απορρίψεων"))
    st.plotly_chart(px.histogram(filtered, x="industry", color="apofasi", barmode="group", title="Αποφάσεις ανά κλάδο"))
    st.plotly_chart(px.box(filtered, x="industry", y="score", title="Scores ανά κλάδο"))

# -- Show audit log (admin only)
if is_admin and os.path.exists(AUDIT_FILE):
    st.subheader("🕵️ Audit Trail / Log ενεργειών")
    log_df = pd.read_csv(AUDIT_FILE)
    st.dataframe(log_df)

# --- API stub (for future ICAP/trust signals connections)
st.sidebar.header("🔗 API (demo)")
api_integration = st.sidebar.button("Fetch ICAP ή άλλα scores μέσω API (demo λειτουργία)")
if api_integration:
    st.sidebar.info("Θα μπορούσες εδώ να τραβήξεις τιμές κατευθείαν από ICAP API ή τράπεζα!")

