import tables as tb

class MetaTable(tb.IsDescription):
    start_index = tb.UInt32Col(pos=0)
    stop_index = tb.UInt32Col(pos=1)
    length = tb.UInt32Col(pos=2)
    # https://github.com/PyTables/PyTables/issues/230
    #timestamp = tb.Time64Col(pos=3)
    timestamp = tb.Float64Col(pos=3)
    error = tb.UInt32Col(pos=4)

class HitInfoTable(tb.IsDescription):
    event_number = tb.UInt32Col(pos=0)
    trigger_number = tb.UInt32Col(pos=1)
    relative_BCID = tb.UInt8Col(pos=2)
    LVLID = tb.UInt16Col(pos=3)
    column = tb.UInt8Col(pos=4)
    row = tb.UInt16Col(pos=5)
    tot = tb.UInt8Col(pos=6)
    BCID = tb.UInt16Col(pos=7)
    trigger_status = tb.UInt8Col(pos=8)
    service_record = tb.UInt32Col(pos=9)
    event_status = tb.UInt8Col(pos=10)
    
class MetaInfoOutTable(tb.IsDescription):
    event_number = tb.UInt32Col(pos=0)
    time_stamp = tb.Float64Col(pos=1)
    error_code = tb.UInt32Col(pos=2)
    
class ClusterHitInfoTable(tb.IsDescription):
    event_number = tb.UInt32Col(pos=0)
    trigger_number = tb.UInt32Col(pos=1)
    relative_BCID = tb.UInt8Col(pos=2)
    LVLID = tb.UInt16Col(pos=3)
    column = tb.UInt8Col(pos=4)
    row = tb.UInt16Col(pos=5)
    tot = tb.UInt8Col(pos=6)
    BCID = tb.UInt16Col(pos=7)
    trigger_status = tb.UInt8Col(pos=8)
    service_record = tb.UInt32Col(pos=9)
    event_status = tb.UInt8Col(pos=10)
    cluster_id = tb.UInt16Col(pos=11)
    is_seed = tb.UInt8Col(pos=12)
    
class ClusterInfoTable(tb.IsDescription):
    event_number = tb.UInt32Col(pos=0)
    id = tb.UInt16Col(pos=1)
    size = tb.UInt16Col(pos=2)
    tot = tb.UInt16Col(pos=3)
    charge = tb.Float32Col(pos=4)
    seed_column = tb.UInt8Col(pos=5)
    seed_row = tb.UInt16Col(pos=6)
    event_status = tb.UInt8Col(pos=7)

