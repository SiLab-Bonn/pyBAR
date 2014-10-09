import pstats

p = pstats.Stats('profile')

p.sort_stats('time').print_stats(20)
p.sort_stats('cumulative').print_stats(20)