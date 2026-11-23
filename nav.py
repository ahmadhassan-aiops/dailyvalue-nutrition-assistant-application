"""Page registry (label tabs, native navigation hidden)."""

import streamlit as st

from views import ask, method, quality, shelf

ASK = st.Page(ask.render, title="Ask", icon=":material/forum:", url_path="ask", default=True)
SHELF = st.Page(shelf.render, title="Shelf", icon=":material/menu_book:", url_path="shelf")
QUALITY = st.Page(quality.render, title="Quality", icon=":material/fact_check:", url_path="quality")
METHOD = st.Page(method.render, title="Method", icon=":material/account_tree:", url_path="method")

PAGES = [ASK, SHELF, QUALITY, METHOD]
