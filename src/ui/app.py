import streamlit as st
import pandas as pd
import asyncio
import os
import sys
import math

# Add project root to sys.path to handle imports when running from subdirectories
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from sqlalchemy import select
from src.storage.database import init_db, get_session_factory, Listing, Agent
from src.utils.config import AppSettings


# Page config
st.set_page_config(page_title="LuxeLink", page_icon="💎", layout="wide")

# Load settings
settings = AppSettings()


async def get_listings():
    engine = await init_db(settings.DATABASE_URL)
    session_factory = get_session_factory(engine)
    async with session_factory() as session:
        stmt = select(Listing).order_by(Listing.first_seen.desc())
        result = await session.execute(stmt)
        return result.scalars().all()


async def get_agents():
    engine = await init_db(settings.DATABASE_URL)
    session_factory = get_session_factory(engine)
    async with session_factory() as session:
        stmt = select(Agent)
        result = await session.execute(stmt)
        return result.scalars().all()


def main():
    # Logo and Title
    logo_path = "Public/LuxeLink-Logo_upscayl_2x_digital-art-4x_upscayl_2x_digital-art-4x.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=300)

    st.title("LuxeLink Dashboard")
    st.markdown(
        "Monitor high-end vehicle listings across multiple marketplaces and keep your clients' search profiles in sync."
    )
    st.markdown("---")

    # Sidebar
    if os.path.exists(logo_path):
        st.sidebar.image(logo_path, width="stretch")
    st.sidebar.header("Controls")
    if st.sidebar.button("🔄 Refresh Data"):
        st.rerun()

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📋 Found Listings", "🤖 Search Profiles", "➕ Add Profile", "⚙️ Configuration"]
    )

    with tab1:
        st.header("Recent Matches")
        listings = asyncio.run(get_listings())

        if not listings:
            st.info("No listings found yet. Run an agent to start searching!")
        else:
            total = len(listings)
            sources = sorted({l.source for l in listings})
            latest_seen = max(l.first_seen for l in listings)

            m1, m2, m3 = st.columns(3)
            m1.metric("Total matches", total)
            m2.metric("Sources", ", ".join(sources) if sources else "—")
            m3.metric("Last updated", latest_seen.strftime("%Y-%m-%d %H:%M"))

            st.markdown("### Browse listings")

            # Build a typed dataframe for filtering/sorting (keep numerics as numerics).
            rows = []
            for l in listings:
                rows.append(
                    {
                        "listing_id": l.id,
                        "agent_id": l.agent_id,
                        "external_id": l.external_id,
                        "first_seen": l.first_seen,
                        "year": l.year,
                        "make": l.make,
                        "model": l.model,
                        "title": l.title,
                        "price": l.price,
                        "mileage": l.mileage,
                        "source": l.source,
                        "match_score": l.match_score,
                        "url": l.url,
                        "raw_json": l.raw_json,
                    }
                )
            df = pd.DataFrame(rows)
            if not df.empty:
                df["year"] = pd.to_numeric(df["year"], errors="coerce")
                df["price"] = pd.to_numeric(df["price"], errors="coerce")
                df["mileage"] = pd.to_numeric(df["mileage"], errors="coerce")
                df["match_score"] = pd.to_numeric(df["match_score"], errors="coerce")

            with st.expander("Filters & view options", expanded=False):
                qf1, qf2, qf3, qf4 = st.columns(4)
                with qf1:
                    q_marketcheck_only = st.checkbox("Marketcheck only", value=False)
                with qf2:
                    q_under_100k = st.checkbox("Under $100k", value=False)
                with qf3:
                    q_under_30k_miles = st.checkbox("Under 30k miles", value=False)
                with qf4:
                    q_last_7_days = st.checkbox("Last 7 days", value=False)

                c1, c2, c3, c4 = st.columns([0.35, 0.25, 0.2, 0.2])
                with c1:
                    keyword = st.text_input(
                        "Keyword (make / model / title)", value="", placeholder="e.g. 911, M3, GT3…"
                    ).strip()
                with c2:
                    selected_sources = st.multiselect(
                        "Source",
                        options=sources,
                        default=sources,
                    )
                with c3:
                    view_mode = st.radio(
                        "View",
                        options=["Table", "Cards"],
                        horizontal=True,
                    )
                with c4:
                    sort_option = st.selectbox(
                        "Sort by",
                        options=[
                            "Newest",
                            "Oldest",
                            "Price: low → high",
                            "Price: high → low",
                            "Mileage: low → high",
                            "Mileage: high → low",
                            "Match score: high → low",
                        ],
                        index=0,
                    )

                r1, r2, r3 = st.columns(3)
                with r1:
                    year_min = st.number_input("Year min", min_value=1900, max_value=2100, value=1900)
                    year_max = st.number_input("Year max", min_value=1900, max_value=2100, value=2100)
                with r2:
                    price_min = st.number_input("Price min ($)", min_value=0, value=0, step=1000)
                    price_max = st.number_input("Price max ($)", min_value=0, value=0, step=1000, help="0 = no max")
                with r3:
                    miles_min = st.number_input("Mileage min", min_value=0, value=0, step=1000)
                    miles_max = st.number_input("Mileage max", min_value=0, value=0, step=1000, help="0 = no max")

            # Apply filters
            f = df.copy()

            # Quick filters
            if q_marketcheck_only:
                f = f[f["source"] == "marketcheck"]
            if q_under_100k:
                f = f[(f["price"].isna()) | (f["price"] <= 100_000)]
            if q_under_30k_miles:
                f = f[(f["mileage"].isna()) | (f["mileage"] <= 30_000)]
            if q_last_7_days:
                cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=7)
                f = f[f["first_seen"] >= cutoff.to_pydatetime()]

            if selected_sources:
                f = f[f["source"].isin(selected_sources)]

            if keyword:
                needle = keyword.lower()
                text = (
                    f["make"].fillna("").astype(str)
                    + " "
                    + f["model"].fillna("").astype(str)
                    + " "
                    + f["title"].fillna("").astype(str)
                ).str.lower()
                f = f[text.str.contains(needle, na=False)]

            if year_min:
                f = f[(f["year"].isna()) | (f["year"] >= year_min)]
            if year_max and year_max < 2100:
                f = f[(f["year"].isna()) | (f["year"] <= year_max)]

            if price_min and price_min > 0:
                f = f[(f["price"].isna()) | (f["price"] >= price_min)]
            if price_max and price_max > 0:
                f = f[(f["price"].isna()) | (f["price"] <= price_max)]

            if miles_min and miles_min > 0:
                f = f[(f["mileage"].isna()) | (f["mileage"] >= miles_min)]
            if miles_max and miles_max > 0:
                f = f[(f["mileage"].isna()) | (f["mileage"] <= miles_max)]

            # Sorting
            if sort_option == "Newest":
                f = f.sort_values("first_seen", ascending=False)
            elif sort_option == "Oldest":
                f = f.sort_values("first_seen", ascending=True)
            elif sort_option == "Price: low → high":
                f = f.sort_values(["price", "first_seen"], ascending=[True, False], na_position="last")
            elif sort_option == "Price: high → low":
                f = f.sort_values(["price", "first_seen"], ascending=[False, False], na_position="last")
            elif sort_option == "Mileage: low → high":
                f = f.sort_values(["mileage", "first_seen"], ascending=[True, False], na_position="last")
            elif sort_option == "Mileage: high → low":
                f = f.sort_values(["mileage", "first_seen"], ascending=[False, False], na_position="last")
            elif sort_option == "Match score: high → low":
                f = f.sort_values(["match_score", "first_seen"], ascending=[False, False], na_position="last")

            # Pagination controls
            p1, p2, p3 = st.columns([0.25, 0.25, 0.5])
            with p1:
                page_size = st.selectbox("Rows per page", options=[25, 50, 100, 200], index=1)
            total_rows = int(len(f))
            total_pages = max(1, math.ceil(total_rows / page_size))
            with p2:
                page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
            with p3:
                st.caption(f"Showing {total_rows:,} match(es) • Page {int(page)} of {total_pages}")

            start = (int(page) - 1) * page_size
            end = start + page_size
            page_df = f.iloc[start:end].copy()

            def extract_image_urls(raw_json: object) -> list[str]:
                urls: list[str] = []

                def normalize(u: object) -> str | None:
                    if not isinstance(u, str):
                        return None
                    s = u.strip().strip('"').strip("'")
                    # Some providers prefix with '%20' or other junk before the real URL.
                    if "http" in s and not s.startswith("http"):
                        s = s[s.find("http") :]
                    if not s.startswith("http"):
                        return None
                    # Strip trailing size hints like " 320w" or "%20320w"
                    for sep in ["%20", " "]:
                        if sep in s:
                            s = s.split(sep, 1)[0]
                    if s.endswith(("w", "w\"")):
                        # best-effort cleanup; final safety check relies on HTTP response
                        pass
                    return s

                if not isinstance(raw_json, dict):
                    return urls

                # Common shapes across providers/APIs
                for key in ("images", "image_urls", "photo_links", "photos"):
                    v = raw_json.get(key)
                    if isinstance(v, list):
                        for u in v:
                            cleaned = normalize(u)
                            if cleaned:
                                urls.append(cleaned)

                media = raw_json.get("media")
                if isinstance(media, dict):
                    for key in ("photo_links", "images"):
                        v = media.get(key)
                        if isinstance(v, list):
                            for u in v:
                                cleaned = normalize(u)
                                if cleaned:
                                    urls.append(cleaned)
                # Many providers return the same image in multiple sizes (e.g. 320/640/960/1280).
                # Group by folder and keep the largest-size URL per folder.
                best_by_folder: dict[str, tuple[int, str]] = {}
                for u in urls:
                    try:
                        folder, filename = u.rsplit("/", 1)
                    except ValueError:
                        folder, filename = "", u
                    digits = "".join(ch for ch in filename if ch.isdigit())
                    width = int(digits) if digits else 0
                    prev = best_by_folder.get(folder)
                    if not prev or width > prev[0]:
                        best_by_folder[folder] = (width, u)
                # Preserve insertion order of folders
                return [val[1] for _, val in best_by_folder.items()]

            def fmt_money(v):
                if pd.isna(v):
                    return "Contact"
                try:
                    return f"${float(v):,.0f}"
                except Exception:
                    return "Contact"

            def fmt_int(v, suffix=""):
                if pd.isna(v):
                    return "N/A"
                try:
                    return f"{int(float(v)):,}{suffix}"
                except Exception:
                    return "N/A"

            def render_listing_details(row: pd.Series):
                title = (row.get("title") or "").strip()
                st.markdown(f"**{title if title else 'Listing'}**")

                url = row.get("url") or ""
                if url:
                    st.markdown(f"[Open listing]({url})")

                d1, d2, d3, d4 = st.columns([0.25, 0.25, 0.25, 0.25])
                d1.metric("Year", fmt_int(row.get("year")))
                d2.metric("Price", fmt_money(row.get("price")))
                d3.metric("Mileage", fmt_int(row.get("mileage"), " mi"))
                d4.metric("Score", fmt_int(row.get("match_score")) if not pd.isna(row.get("match_score")) else "—")

                meta1, meta2, meta3 = st.columns([0.4, 0.3, 0.3])
                meta1.caption(f"Source: {row.get('source') or '—'}")
                meta2.caption(f"Agent: {row.get('agent_id') or '—'}")
                meta3.caption(f"Found: {row.get('first_seen')}")

                raw_json = row.get("raw_json")
                imgs = extract_image_urls(raw_json)
                if imgs:
                    st.markdown("**Photos**")
                    st.image(imgs[:6], width=300)

                with st.expander("Raw data (advanced)"):
                    st.json(raw_json if isinstance(raw_json, dict) else {"raw_json": raw_json})

            if view_mode == "Table":
                display = pd.DataFrame(
                    {
                        "Date Found": page_df["first_seen"].dt.strftime("%Y-%m-%d %H:%M")
                        if hasattr(page_df["first_seen"], "dt")
                        else page_df["first_seen"].astype(str),
                        "Year": page_df["year"].apply(lambda x: fmt_int(x) if not pd.isna(x) else "N/A"),
                        "Title": page_df["title"].fillna(""),
                        "Price": page_df["price"].apply(fmt_money),
                        "Mileage": page_df["mileage"].apply(lambda x: fmt_int(x, " mi")),
                        "Source": page_df["source"].fillna(""),
                        "Score": page_df["match_score"].apply(lambda x: fmt_int(x) if not pd.isna(x) else "—"),
                        "URL": page_df["url"].fillna(""),
                    }
                )
                st.dataframe(
                    display,
                    column_config={"URL": st.column_config.LinkColumn("Listing Link")},
                    hide_index=True,
                    width="stretch",
                )

                st.markdown("### Inspect a listing")
                if page_df.empty:
                    st.info("No listings to inspect on this page.")
                else:
                    options = []
                    for _, r in page_df.iterrows():
                        year_str = fmt_int(r.get("year")) if not pd.isna(r.get("year")) else "N/A"
                        price_str = fmt_money(r.get("price"))
                        options.append(
                            (
                                f"{year_str} • {price_str} • {r.get('source') or '—'} • {(r.get('title') or '')[:80]}",
                                r.get("listing_id"),
                            )
                        )
                    label_to_id = {lbl: lid for lbl, lid in options}
                    selected_label = st.selectbox(
                        "Choose a listing on this page",
                        options=[lbl for lbl, _ in options],
                    )
                    sel_id = label_to_id.get(selected_label)
                    selected_row = page_df[page_df["listing_id"] == sel_id].iloc[0]
                    with st.container(border=True):
                        render_listing_details(selected_row)
            else:
                if page_df.empty:
                    st.info("No listings match your filters.")
                else:
                    cols = st.columns(2)
                    for idx, (_, row) in enumerate(page_df.iterrows()):
                        with cols[idx % 2]:
                            with st.container(border=True):
                                title = (row.get("title") or "").strip()
                                year_str = fmt_int(row.get("year")) if not pd.isna(row.get("year")) else "N/A"
                                price_str = fmt_money(row.get("price"))
                                miles_str = fmt_int(row.get("mileage"), " mi")
                                source_str = row.get("source") or "—"
                                score_str = (
                                    fmt_int(row.get("match_score"))
                                    if not pd.isna(row.get("match_score"))
                                    else "—"
                                )
                                url = row.get("url") or ""

                                st.markdown(f"**{year_str} — {title}**")
                                a, b, c = st.columns(3)
                                a.metric("Price", price_str)
                                b.metric("Mileage", miles_str)
                                c.metric("Score", score_str)

                                st.caption(f"Source: {source_str}")
                                if url:
                                    st.markdown(f"[View listing]({url})")
                                with st.expander("Details"):
                                    render_listing_details(row)

    with tab2:
        st.header("Active Search Profiles")
        agents = asyncio.run(get_agents())
        if not agents:
            st.warning("No search profiles found. Create one in the 'Add Profile' tab!")
        else:
            for agent in agents:
                cfg = agent.config_json or {}
                params = cfg.get("parameters", {})
                vehicles = params.get("vehicles", [])

                if vehicles:
                    vehicle_labels = ", ".join(
                        f"{v.get('make', '')} {v.get('model', '')}".strip()
                        for v in vehicles[:4]
                    )
                    if len(vehicles) > 4:
                        vehicle_labels += f" (+{len(vehicles) - 4} more)"
                else:
                    vehicle_labels = "Any"

                loc = params.get("location") or {}
                loc_str = ""
                if loc.get("zip"):
                    radius = loc.get("radius_miles")
                    if radius:
                        loc_str = f"{loc.get('zip')} ± {radius} mi"
                    else:
                        loc_str = loc.get("zip")

                sources = ", ".join(cfg.get("sources", [])) or "—"
                emails = cfg.get("notifications", {}).get("email_to", [])

                col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
                with col1:
                    with st.expander(
                        f"{agent.name} ({'Enabled' if agent.enabled else 'Disabled'})"
                    ):
                        st.markdown(f"**Profile ID:** `{agent.id}`")
                        st.markdown(f"**Vehicles:** {vehicle_labels}")
                        if loc_str:
                            st.markdown(f"**Location:** {loc_str}")
                        st.markdown(f"**Sources:** {sources}")
                        if emails:
                            st.markdown(f"**Emails:** {', '.join(emails)}")

                with col2:
                    if st.button(f"Run Now", key=f"run_{agent.id}"):
                        st.info(f"Triggering run for {agent.name}...")
                        # In a real app, we'd use a task queue.
                        st.success("Run triggered!")

                with col3:
                    status_label = "Disable" if agent.enabled else "Enable"
                    if st.button(status_label, key=f"toggle_{agent.id}"):
                        async def toggle_agent(aid, current_status):
                            engine = await init_db(settings.DATABASE_URL)
                            session_factory = get_session_factory(engine)
                            async with session_factory() as session:
                                db_agent = await session.get(Agent, aid)
                                if db_agent:
                                    db_agent.enabled = not current_status
                                    cfg = db_agent.config_json.copy()
                                    cfg["enabled"] = not current_status
                                    db_agent.config_json = cfg
                                    await session.commit()

                        asyncio.run(toggle_agent(agent.id, agent.enabled))
                        st.rerun()

                    if st.button("🗑️ Delete", key=f"del_{agent.id}"):
                        async def delete_agent(aid):
                            engine = await init_db(settings.DATABASE_URL)
                            session_factory = get_session_factory(engine)
                            async with session_factory() as session:
                                db_agent = await session.get(Agent, aid)
                                if db_agent:
                                    await session.delete(db_agent)
                                    await session.commit()

                        asyncio.run(delete_agent(agent.id))
                        st.success("Profile deleted!")
                        st.rerun()

    with tab3:
        st.header("Create New Search Profile")
        with st.form("new_profile_form"):
            profile_name = st.text_input("Profile Name (e.g., Client: John Doe)")
            profile_id = profile_name.lower().replace(" ", "_")

            st.subheader("Vehicle Criteria")
            col1, col2, col3 = st.columns(3)
            with col1:
                make = st.text_input("Make")
            with col2:
                model = st.text_input("Model")
            with col3:
                year_min = st.number_input(
                    "Min Year", min_value=1900, max_value=2026, value=2020
                )

            st.subheader("Location")
            lcol1, lcol2 = st.columns(2)
            with lcol1:
                zip_code = st.text_input("Zip Code", value="60601")
            with lcol2:
                radius = st.number_input("Radius (miles)", value=500)

            sources = st.multiselect(
                "Sources",
                ["bringatrailer", "cars_com", "carfax", "autonation", "marketcheck"],
                default=["cars_com", "carfax"],
            )

            submit = st.form_submit_button("Create Profile")

            if submit and profile_name and make and model:
                new_config = {
                    "id": profile_id,
                    "name": profile_name,
                    "enabled": True,
                    "parameters": {
                        "vehicles": [
                            {"make": make, "model": model, "year_min": year_min}
                        ],
                        "location": {"zip": zip_code, "radius_miles": radius},
                    },
                    "sources": sources,
                    "notifications": {"email_to": [settings.GMAIL_USER]},
                }

                async def save_profile(cfg):
                    engine = await init_db(settings.DATABASE_URL)
                    session_factory = get_session_factory(engine)
                    async with session_factory() as session:
                        new_agent = Agent(
                            id=cfg["id"],
                            name=cfg["name"],
                            enabled=True,
                            config_json=cfg,
                        )
                        session.add(new_agent)
                        await session.commit()

                asyncio.run(save_profile(new_config))
                st.success(f"Profile '{profile_name}' created successfully!")
                st.rerun()

    with tab4:
        st.header("System Configuration")
        st.write(
            "**Database URL (masked):**", settings.DATABASE_URL.split("@")[-1]
        )  # Hide credentials
        st.write("**Gmail User:**", settings.GMAIL_USER)
        st.write("**Log Level:**", settings.LOG_LEVEL)

        if os.path.exists("config/agents.yaml"):
            st.subheader("Search profiles configuration")
            st.caption(
                "These profiles are initially loaded from `config/agents.yaml` and then stored in the database."
            )
            with st.expander("View raw agents.yaml"):
                with open("config/agents.yaml", "r") as f:
                    st.code(f.read(), language="yaml")


if __name__ == "__main__":
    main()
