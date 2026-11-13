from django.conf import settings


def google_maps(request):
    return {"GOOGLE_MAPS_KEY": getattr(settings, "GOOGLE_MAPS_KEY", "")}


def mobile_ws_config(request):
    """
    Provides WebSocket and server configuration for mobile and web clients.
    Ensures correct host/port are used for cross-device communication.
    """
    # Get server configuration
    server_ip = getattr(settings, 'SERVER_IP', 'localhost')
    server_port = getattr(settings, 'SERVER_PORT', '8000')
    ws_protocol = getattr(settings, 'WS_PROTOCOL', 'ws')
    
    # Build WebSocket URL - use request.get_host() for web clients,
    # but also provide SERVER_IP for mobile clients to override if needed
    host = request.get_host().split(':')[0]  # Get hostname without port
    
    # Primary WebSocket URL (for web clients accessing from same network)
    ws_url = f"{ws_protocol}://{request.get_host()}"
    
    # Fallback WebSocket URL (for mobile clients - uses configured SERVER_IP)
    ws_url_mobile = f"{ws_protocol}://{server_ip}:{server_port}"
    
    return {
        'WS_URL': ws_url,
        'WS_URL_MOBILE': ws_url_mobile,
        'SERVER_IP': server_ip,
        'SERVER_PORT': server_port,
    }
