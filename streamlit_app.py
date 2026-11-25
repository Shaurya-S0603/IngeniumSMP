import streamlit as st
from mcstatus import JavaServer
from datetime import datetime, timezone

st.set_page_config(page_title="Ingenium SMP", page_icon="🔥",layout="wide")
st.markdown("""
<style>
.stApp { background: #140d0e; color: #f5e9e5; }
[data-testid="stMetric"] {background:#261619;padding:16px;border:1px solid #67302c;border-radius:12px;}
[data-testid="stMetricLabel"],[data-testid="stMetricValue"] {color:#fff0e7;}
h1,h2,h3 {color:#ffad82;}
</style>
""",unsafe_allow_html=True)

def setting(key):
    try:
        return str(st.secrets.get(key,"")).strip()
    except Exception:
        return ""

address=setting("server_address")
invite=setting("discord_invite")

@st.cache_data(ttl=20,show_spinner=False)
def query(address):
    if not address:
        return {"state":"Not configured"}
    try:
        s=JavaServer.lookup(address,timeout=4).status()
        return {"state":"Online","count":s.players.online,"max":s.players.max,"latency":round(s.latency),"version":s.version.name,"checked":datetime.now(timezone.utc).isoformat(timespec="seconds")}
    except Exception:
        return {"state":"Unreachable","checked":datetime.now(timezone.utc).isoformat(timespec="seconds")}

st.title("INGENIUM SMP")
st.markdown("**THE FORGE | SERVER HUB**")
st.caption("SURVIVAL • EXPLORATION • COMMUNITY")
st.write("Minecraft Java 26.3 | Vanilla+ | Private whitelist")
@st.fragment(run_every="30s")
def live_status():
    if st.button("Refresh status"):
        query.clear()
    data=query(address)
    a,b,c,d=st.columns(4)
    a.metric("Server",data["state"])
    b.metric("Players",f'{data["count"]}/{data["max"]}' if "count" in data else "—")
    c.metric("Latency",f'{data["latency"]} ms' if "latency" in data else "—")
    d.metric("Datapacks",6)
    if "checked" in data:
        st.caption("Last checked: "+data["checked"]+" | Latency measured from dashboard, not your device.")
    if data["state"]=="Unreachable":
        st.info("The Minecraft server or tunnel is not responding. The laptop may be asleep, offline or restarting.")
    if "version" in data:
        st.caption("Reported server version: "+data["version"])
    st.caption("Auto-refreshes every 30 seconds while this page is open.")

live_status()

st.subheader("Join the SMP")
if address:
    st.code(address,language=None)
else:
    st.info("The host has not configured the public address yet.")
st.write("Use Java Edition 26.3. Ask an administrator to whitelist your exact username and arrange authentication before connecting.")
if invite.startswith("https://discord.gg/") or invite.startswith("https://discord.com/invite/"):
    st.link_button("Join Ingenium SMP Discord",invite)
st.caption("IngeniumBot handles staff controls through Discord. This dashboard is read-only.")

st.subheader("World and datapacks")
packs=[
    ("Terralith","2.6.5 + 26.3","Overworld terrain and biomes"),
    ("Terralith ReStoned","1.3.1","Terralith companion pack"),
    ("Incendium Legacy","5.5.4 + 26.3","Nether generation"),
    ("Nullscape","2.0.1 + 26.3","End generation"),
    ("OreVeinMiner","3.2.0 + 26.3","Ore vein mining"),
    ("TreeVeinMiner","4.3.2 + 26.3","Tree harvesting"),
]
for index in range(0,len(packs),2):
    for col,(name,version,description) in zip(st.columns(2),packs[index:index+2]):
        with col:
            with st.container(border=True):
                st.markdown("**"+name+"**")
                st.caption(version)
                st.write(description)
st.caption("Catalogue based on the original Aternos export; enabled status requires local server verification.")
st.divider()
st.caption("Ingenium SMP • Dashboard availability does not imply Minecraft availability.")
