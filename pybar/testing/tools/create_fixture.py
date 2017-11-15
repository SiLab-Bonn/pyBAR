''' Script to reduce data files to create unit test fixtures.
'''

import tables as tb


def create_fixture(file_in, file_out, n_readouts, nodes):
    with tb.open_file(file_in, 'r') as in_file:
        with tb.open_file(file_out, 'w') as out_file:
            in_file.copy_node('/configuration', out_file.root, recursive=True)
            start, stop = None, None
            if 'meta_data' in nodes:
                node = in_file.get_node('/meta_data')
                meta_data = node[:n_readouts]
                try:
                    start, stop = meta_data['index_start'][0], meta_data['index_stop'][-1]
                except IndexError:
                    start, stop = meta_data['hit_start'][0], meta_data['hit_stop'][-1]
                t = out_file.create_table(out_file.root, name=node.name, description=node.description, filters=node.filters)
                t.append(meta_data)
            for n in nodes:
                if n == 'meta_data':
                    continue
                node = in_file.get_node('/' + n)
                data = node[start:stop]
                if type(node) == tb.earray.EArray:
                    earray = out_file.create_earray(out_file.root, name=node.name, atom=tb.UIntAtom(), shape=(0,), title=node.title, filters=node.filters)
                    earray.append(data)

if __name__ == '__main__':
    create_fixture(file_in=r'H:\Testbeam_07032016_LFCMOS\original_data\LFCMOS_1_14Neq\lfcmos_3_efficiency\117_lfcmos_3_ext_trigger_scan.h5',
                   file_out='small.h5',
                   n_readouts=100,
                   nodes=['raw_data', 'meta_data'])
