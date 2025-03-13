# imghdr.py - Implémentation minimale pour satisfaire la dépendance de telegram

def what(filename, h=None):
    """
    Fonction minimaliste pour déterminer le type d'image.
    Elle reconnaît les formats JPEG, PNG et GIF.
    """
    if h is None:
        try:
            with open(filename, "rb") as f:
                h = f.read(32)
        except Exception:
            return None

    if h.startswith(b'\xff\xd8'):
        return 'jpeg'
    if h.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if h[0:3] == b'GIF':
        return 'gif'
    return None
