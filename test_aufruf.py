# Test-Aufruf für das UI
if st.button("Test: Frage in SQL übersetzen"):
    test_frage = "Wer stellt ASS her?" # Oder deine Eingabe-Variable
    generiertes_sql = uebersetze_frage_in_sql(test_frage, db_schema)
    st.code(generiertes_sql, language="sql")