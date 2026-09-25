import os
import sys
import traceback

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saascourse.settings')

try:
    from django.core.wsgi import get_wsgi_application
    _django_app = get_wsgi_application()

    def application(environ, start_response):
        try:
            return _django_app(environ, start_response)
        except Exception:
            err_msg = traceback.format_exc() 
            try:
                with open(os.path.join(CURRENT_DIR, "passenger_error.log"), "a", encoding="utf-8") as f:
                    f.write("\n--- RUNTIME ERROR ---\n" + err_msg)
            except Exception:
                pass
            status = '500 Internal Server Error'
            response_headers = [('Content-Type', 'text/html; charset=utf-8')]
            start_response(status, response_headers)
            body = f"<html><head><title>Application Runtime Error</title></head><body><h2>Django Runtime Error</h2><pre style='background:#f8f9fa;padding:15px;border:1px solid #dee2e6;border-radius:6px;'>{err_msg}</pre></body></html>"
            return [body.encode('utf-8')]

except Exception:
    err_msg = traceback.format_exc()
    try:
        with open(os.path.join(CURRENT_DIR, "passenger_error.log"), "a", encoding="utf-8") as f:
            f.write("\n--- STARTUP ERROR ---\n" + err_msg)
    except Exception:
        pass

    def application(environ, start_response):
        status = '500 Internal Server Error'
        response_headers = [('Content-Type', 'text/html; charset=utf-8')]
        start_response(status, response_headers)
        body = f"<html><head><title>Application Startup Error</title></head><body><h2>Django Startup Error</h2><pre style='background:#f8f9fa;padding:15px;border:1px solid #dee2e6;border-radius:6px;'>{err_msg}</pre></body></html>"
        return [body.encode('utf-8')]