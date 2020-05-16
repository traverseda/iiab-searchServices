from flask import Flask, request, send_from_directory, render_template, redirect
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
import api
from settings import THEME

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

@app.route('/search/')
def search():
    db.reopen()
    q = request.args.get('q','')
    if "!g" in q or "!google" in q:
        #Redirect to google, like duck duck go.
        return redirect("https://google.ca/search?q="+q.replace("!g","").replace("!google",""))

    page = int(request.args.get('page','1'))-1
    pageSize = int(request.args.get('pageSize','8'))

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
    run_simple('localhost', 8000, server,
               use_reloader=True, use_debugger=True, use_evalex=True)


