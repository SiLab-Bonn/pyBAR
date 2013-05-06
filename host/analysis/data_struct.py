import tables as tb


class MetaTable(tb.IsDescription):
    start_index = tb.UInt32Col(pos=0)
    stop_index = tb.UInt32Col(pos=1)
    length = tb.UInt32Col(pos=2)
    # https://github.com/PyTables/PyTables/issues/230
    #timestamp = tb.Time64Col(pos=3)
    timestamp = tb.Float64Col(pos=3)
    error = tb.UInt32Col(pos=4)

