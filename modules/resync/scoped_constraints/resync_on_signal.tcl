# ------------------------------------------------------------------------------
# Copyright (c) Lukas Vik. All rights reserved.
# ------------------------------------------------------------------------------

set data_out [get_cells data_out_reg]
set data_in [get_nets data_in_int]

set_false_path -setup -hold -through ${data_in} -to ${data_out}