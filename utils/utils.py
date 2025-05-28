from datetime import datetime, date

def datetime_serializer(obj):
    if isinstance(obj, (datetime, date)): 
        return obj.isoformat() 
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def send_msg(msg: str, **kwargs: any) -> dict[str, any]:
    response = {
        "msg" : msg
    } 
    response.update(kwargs)
    return response