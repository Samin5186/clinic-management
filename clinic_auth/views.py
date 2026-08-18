import traceback
from django.http import HttpResponse


def custom_500(request, *args, **kwargs):
    try:
        exc = args[0] if args else kwargs.get('exception')
        tb = traceback.format_exc()
        with open('server.log', 'a') as f:
            f.write(f"\n=== 500 ERROR ===\n")
            f.write(f"Path: {request.path}\n")
            f.write(f"User: {request.user}\n")
            f.write(f"Exception: {exc}\n")
            f.write(f"{tb}\n")
            f.write(f"=== END 500 ===\n")
    except Exception:
        pass
    return HttpResponse('<h1>500 - Server Error</h1><p>Please try again in a moment.</p>', status=500)
