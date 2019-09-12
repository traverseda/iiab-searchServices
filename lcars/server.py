from flask import Flask, request, send_from_directory, render_template, redirect
from settings import config

# set the project root directory as the static folder, you can set others.
app = Flask(__name__, static_url_path='/static/')

@app.context_processor
def inject_settings_theme():
    return dict(theme=config['Theme'])

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

import xapian
db = xapian.Database(config['Search']['index_dir'])

import xapian
queryparser = xapian.QueryParser()
queryparser.set_stemmer(xapian.Stem("en"))
queryparser.set_stemming_strategy(queryparser.STEM_SOME)
queryparser.set_database(db)
queryparser.add_boolean_prefix("url","Q")

flags = queryparser.FLAG_DEFAULT|queryparser.FLAG_SPELLING_CORRECTION

import json, math

@app.route('/search/')
def search():
    db.reopen()
    q = request.args.get('q','')
    if "!g" in q or "!google" in q:
        #Redirect to google, like duck duck go.
        return redirect("https://google.ca/search?q="+q.replace("!g","").replace("!google",""))

    query = queryparser.parse_query(q, flags)

    enquire = xapian.Enquire(db)
    enquire.set_query(query)
    page = int(request.args.get('page','1'))-1
    pageSize = int(request.args.get('pageSize','20'))
    matches = enquire.get_mset(page, pageSize)
    matchData = map(json.loads,(m.document.get_data().decode("utf-8") for m in matches))

    pages = math.ceil(matches.get_matches_estimated()/pageSize)

    correction = queryparser.get_corrected_query_string()
    t = render_template("search.html",
                            query=query,
                            pages=pages,
                            correction=correction,
                            matches=matches,
                            matchData=matchData,
                        )

    if not matchData: return t, 404
    return t

@app.route('/')
def home():
    return render_template("home.html")

if __name__ == "__main__":
    app.run()


