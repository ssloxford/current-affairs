from __future__ import annotations

import datetime
import subprocess
import os
from quart import Quart, request, jsonify, redirect, abort, render_template, send_file
import logging
import shutil
import asyncio
from code.network import ui_link_harness

logging.basicConfig()

RESULTS_BASE_FOLDER = "results"
RESULTS_SUB_FOLDER = "experiments"

process: None | subprocess.Popen = None

def in_directory(full_path, directory):
    #make both absolute    
    directory = os.path.join(os.path.realpath(directory), '')

    #return true, if the common prefix of both is equal to directory
    #e.g. /a/b/c/d.rst and directory is /a/b, the common prefix is /a/b
    common_prefix = os.path.commonprefix([full_path, directory])
    return common_prefix == directory

async def main_webserver():
    app = Quart(__name__)

    async def serve_static(req_path, base, download):
        # Joining the base and the requested path
        abs_path = os.path.join(base, req_path)

        verify_abs_path = abs_path
        if os.path.isdir(abs_path):
            verify_abs_path = os.path.join(abs_path, "")

        # Return 403
        if not in_directory(verify_abs_path, base):
            return abort(403)

        # Return 404 if path doesn't exist
        if not os.path.exists(abs_path):
            return abort(404)

        # Check if path is a file and serve
        if os.path.isfile(abs_path):
            print("_".join(req_path.split("/")[-2:]))
            return await send_file(abs_path, as_attachment=download, attachment_filename="_".join(req_path.split("/")[-2:]))
        
        web_base = os.path.join(request.path, "")

        def format_size(size):
            prefixes = ["", "k", "M", "G", "T", "P", "E"]
            for p in prefixes:
                if(size < 1000):
                    if p == "":
                        return f"{size}B"
                    else:
                        return f"{size:.1f}{p}B"
                size /= 1000
            return f"{1000*size:1f}{prefixes[-1]}B"

        # Show directory contents
        files = sorted(os.listdir(abs_path))
        files = [{
            "name": fn,
            "size": format_size(os.path.getsize(os.path.join(abs_path, fn))),
            "isdir": os.path.isdir(os.path.join(abs_path, fn))
            } for fn in files]
        return await render_template("files.html", files=files, base_dir=web_base, parent_dir = os.path.dirname(web_base.rstrip("/")))

    # Route for serving static files
    @app.route('/static/', defaults={'path': ''})
    @app.route('/static/<path>')
    async def serve_static_hander(path):
        return await serve_static(path, os.path.join(os.path.dirname(os.path.realpath(__file__)), "www"), False)

    @app.route(f'/results/', defaults={'path': ''})
    @app.route(f'/results/<path:path>')
    async def serve_results(path):
        return await serve_static(path, os.path.join(os.path.dirname(os.path.realpath(__file__)), RESULTS_BASE_FOLDER), request.args.get('ndl', None) is None)

    @app.route('/shutdown')
    async def handle_shutdown():
        #handle_kill()
        os.system("sudo shutdown -h now")
        return jsonify({})
    
    @app.route('/')
    async def handle_root():
        return redirect("/static/index.html")
    
    @app.route('/upload', methods=['POST'])
    async def upload_file():
        request_files = await request.files
        if 'file' not in request_files:
            return 'No file part'
        file = request_files['file']
        if file.filename == '':
            return 'No selected file'
        if file:
            filename = file.filename
            ext = os.path.splitext(filename)[1]
            new_filename = f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y_%m_%d_%H_%M_%S')}{ext}"
            filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), RESULTS_BASE_FOLDER, "photos", new_filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            await file.save(filepath)
            return f'File successfully uploaded to {filepath}'
        return ""

    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    # Generate with Lets Encrypt, copied to this location, chown to current user and 400 permissions
    ssl_cert = os.path.join(os.path.dirname(os.path.realpath(__file__)),"www/certs/certificate.pem")
    ssl_key = os.path.join(os.path.dirname(os.path.realpath(__file__)),"www/certs/key.pem")

    await app.run_task(host="0.0.0.0", port=8000, certfile=ssl_cert, keyfile=ssl_key)

async def main_websocket():
    harness = ui_link_harness.UI_Harness(os.path.join(os.path.dirname(os.path.realpath(__file__)), RESULTS_BASE_FOLDER, RESULTS_SUB_FOLDER, ""))

    async def websocket_update_task():
        while True:
            await asyncio.sleep(1)
            await harness.state_process.send_state_update()

    asyncio.ensure_future(websocket_update_task())

    await harness.start_websocket_server(True)


async def main():
    print(f"Loaded")

    asyncio.ensure_future(main_websocket())

    await main_webserver()

if __name__ == '__main__':
    asyncio.run(main())
