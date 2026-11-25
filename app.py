"""ISOM3400 Lab 12, adapted from the console extractor with ChatGPT."""

import streamlit as st
from wikipedia_extractor_core import WikipediaExtractor, format_txt, numbered_filename, safe_filename

st.set_page_config(page_title="Wikipedia Extractor", layout="wide")
s = st.session_state
for key, default in dict(topic=None, article=None, titles=[], selected=[], sections=[],
                         downloaded_filenames=[], output=None).items():
    if key not in s:
        s[key] = default


def reset():
    for key in list(s):
        del s[key]
    s.topic_input = ""


def discard_preview():
    s.sections = []
    s.output = None


def remember_download(filename):
    if filename not in s.downloaded_filenames:
        s.downloaded_filenames.append(filename)


if s.article is None and (s.titles or s.sections):
    reset()
    st.rerun()

st.sidebar.header("Wikipedia Extractor")
st.sidebar.button("Start Over", on_click=reset)
st.title("Wikipedia Article Extractor")
with st.expander("How to use this app"):
    st.write("Enter an English Wikipedia article title and press Search. Choose sections, "
             "press Extract to preview them, then download the text file.")

progress = st.empty()
with st.form("search"):
    topic = st.text_input("Enter a topic", placeholder="e.g. Tennis", max_chars=255, key="topic_input")
    submit = st.form_submit_button("Search")

if submit:
    s.topic = topic.strip()
    s.article = None
    s.titles = []
    s.pop("selected", None)
    discard_preview()
    if s.topic:
        with st.spinner("Fetching article…"):
            s.article = WikipediaExtractor(s.topic)
        s.titles = s.article.section_titles()
    else:
        st.warning("Enter an article title.")

article = s.article
if article is not None:
    if article.error:
        st.error(article.error)
    else:
        st.success(article.title)
        st.write(article.url)
        if not s.titles:
            st.warning("This article has no usable top-level sections.")
        else:
            selected = st.multiselect("Select sections", options=s.titles, key="selected",
                                      on_change=discard_preview)
            if st.button("Extract"):
                if selected:
                    s.sections = [article.extract(title) for title in selected]
                    s.output = format_txt(article.title, article.url, s.sections)
                else:
                    st.warning("Select at least one section first.")

if s.sections:
    with st.container(border=True):
        for section in s.sections:
            st.subheader(section["title"])
            if not section["blocks"]:
                st.caption("(No extractable content.)")
            for block in section["blocks"]:
                kind = block["type"]
                if kind == "table":
                    if block["caption"]:
                        st.caption(block["caption"])
                    st.dataframe(block["rows"], hide_index=True)
                elif kind == "list":
                    st.markdown("\n".join(block["lines"]))
                elif kind == "subheading":
                    st.markdown("#### " + block["text"])
                else:
                    st.text(block["text"])
    stem = safe_filename(article.title)
    filename = numbered_filename(stem, s.downloaded_filenames)
    if filename != stem + ".txt":
        st.warning(f"You already downloaded this title in this session. Next file: {filename}")
    st.download_button("Download .txt", data=s.output, file_name=filename, mime="text/plain",
                       key="download_btn", on_click=remember_download, args=(filename,))

with progress.container():
    for column, label, done in zip(st.columns(4), ("Search", "Select", "Extract", "Download"),
                                    (s.titles, s.get("selected"), s.sections, s.downloaded_filenames)):
        column.caption(("✓ " if done else "") + label)
st.caption("Content from Wikipedia, CC BY-SA 4.0.")
with st.expander("Session details"):
    st.write({key: s.get(key) for key in ("topic", "titles", "selected", "downloaded_filenames")})
