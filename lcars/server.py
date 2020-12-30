from flask import Flask, request, send_from_directory, render_template, redirect
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
import lcars.api as api
from lcars.settings import THEME

# set the project root directory as the static folder, you can set others.
app = Flask(__name__, static_url_path='/static/')

server = DispatcherMiddleware(app, {
    "/api":api.__hug_wsgi__,
})

@app.context_processor
def inject_settings_theme():
    return dict(theme=THEME)

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

import json, math
import lcars.api as api

@app.route('/search/')
def search():
    q = request.args.get('q','')
    page = int(request.args.get('page','1'))
    limit = int(request.args.get('limit','10'))
    offset = (page-1)*limit
    if "!g" in q or "!google" in q:
        #Redirect to google, like duck duck go.
        return redirect("https://google.ca/search?q="+q.replace("!g","").replace("!google",""))

    result = api.search(q,offset=offset,limit=limit)

    t = render_template("search.html",
                        searchResult=result,
                        )

    if not result: return t, 404
    return t

@app.route('/')
def home():
    return render_template("home.html")

def main():
    run_simple('localhost', 8000, server,
               use_reloader=True, use_debugger=True, use_evalex=True)

if __name__ == "__main__":
    main()
