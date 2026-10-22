{cts_cmd}
#clock_tree_synthesis -sink_clustering_enable
#clock_tree_synthesis -buf_list {clkbuf_1 clkbuf_2}
{write_cmd}

# --- CTS FLAGS ---
# clock_tree_synthesis:
#   -sink_clustering_enable : Group close sinks to save power and reduce buffer count.
#   -buf_list {...} : Restrict CTS to only use specific buffer cells from the PDK.
