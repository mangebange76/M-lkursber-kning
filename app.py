AttributeError: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).
Traceback:
File "/mount/src/m-lkursber-kning/app.py", line 17, in <module>
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GOOGLE_CREDENTIALS"], scope)
File "/home/adminuser/venv/lib/python3.13/site-packages/oauth2client/service_account.py", line 251, in from_json_keyfile_dict
    return cls._from_parsed_json_keyfile(keyfile_dict, scopes,
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
                                         token_uri=token_uri,
                                         ^^^^^^^^^^^^^^^^^^^^
                                         revoke_uri=revoke_uri)
                                         ^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/oauth2client/service_account.py", line 169, in _from_parsed_json_keyfile
    creds_type = keyfile_dict.get('type')
                 ^^^^^^^^^^^^^^^^
