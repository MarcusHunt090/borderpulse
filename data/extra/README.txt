Drop-in indicator slots. To activate one: create the CSV named in manifest.json
(columns: date,value; date = first of month, YYYY-MM-01) and rerun pipeline.py.
It will appear in the dashboard's watch/community modules with an expanding
z-score. Example: copy food_assistance_TEMPLATE.csv to food_assistance.csv and
replace the rows with real monthly households-served counts.
Nothing here changes the validated composite score — promotion into the index
requires re-running backtest.py and documenting the improvement.
