mkdir -p ~/.streamlit/

echo "\
[general]
email = \"\"\n\
" > ~/.streamlit/credentials.toml

echo "\
[server]
headless = true
enableCORS = false
port = $PORT
" > ~/.streamlit/config.toml
