''' Helper functions for the unittests are defined here.
'''

import numpy as np
import tables as tb


def get_array_differences(first_array, second_array):
    '''Takes two numpy.ndarrays and compares them on a column basis.
    Different column data types, missing columns and columns with different values are returned in a string.

    Parameters
    ----------
    first_array : numpy.ndarray
    second_array : numpy.ndarray

    Returns
    -------
    string
    '''
    if first_array.dtype.names is None:  # normal nd.array
        return ': Sum first array: ' + str(np.sum(first_array)) + ', Sum second array: ' + str(np.sum(second_array))
    else:
        return_str = ''
        for column_name in first_array.dtype.names:
            first_column = first_array[column_name]
            try:
                second_column = second_array[column_name]
            except ValueError:
                return_str += 'No ' + column_name + ' column found. '
                continue
            if (first_column.dtype != second_column.dtype):
                return_str += 'Column ' + column_name + ' has different data type. '
            try:
                if not (first_column == second_column).all():  # check if the data of the column is equal
                    return_str += 'Column ' + column_name + ' not equal. '
            except AttributeError:
                if not (first_column == second_column):
                    return_str += 'Column ' + column_name + ' not equal. '
        for column_name in second_array.dtype.names:
            try:
                first_array[column_name]
            except ValueError:
                return_str += 'Additional column ' + column_name + ' found. '
                continue
        return ': ' + return_str


def array_close(array_1, array_2, rtol=1.e-5, atol=1.e-8):
    '''Compares two numpy arrays elementwise for similarity with small differences.'''
    if not array_1.dtype.names:
        try:
            return np.allclose(array_1, array_2, rtol=1.e-5, atol=1.e-8, equal_nan=True)  # Only works on non recarrays
        except ValueError:  # Raised if shape is incompatible
            return False
    results = []
    for column in array_1.dtype.names:
        results.append(np.allclose(array_1[column], array_2[column], rtol=1.e-5, atol=1.e-8))
    return np.all(results)


def compare_h5_files(first_file, second_file, node_names=None, detailed_comparison=True, exact=True, rtol=1.e-5, atol=1.e-8, chunk_size=1000000):
    '''Takes two hdf5 files and check for equality of all nodes.
    Returns true if the node data is equal and the number of nodes is the number of expected nodes.
    It also returns a error string containing the names of the nodes that are not equal.

    Parameters
    ----------
    first_file : string
        Path to the first file.
    second_file : string
        Path to the second file.
    node_names : list, tuple
        Iterable of node names that are required to exist and will be compared.
        If None, compare all existing nodes and fail if nodes are not existing.
    detailed_comparison : boolean
        Print reason why the comparison failed
    exact : boolean
        True if the results have to match exactly. E.g. False for fit results.
    rtol, atol: number
        From numpy.allclose:
        rtol : float
            The relative tolerance parameter (see Notes).
        atol : float
            The absolute tolerance parameter (see Notes).

    Returns
    -------
    (bool, string)
    '''
    checks_passed = True
    error_msg = ""
    with tb.open_file(first_file, 'r') as first_h5_file:
        with tb.open_file(second_file, 'r') as second_h5_file:
            fist_file_nodes = [node.name for node in first_h5_file.root]  # get node names
            second_file_nodes = [node.name for node in second_h5_file.root]  # get node names
            if node_names is None:
                additional_first_file_nodes = set(fist_file_nodes) - set(second_file_nodes)
                additional_second_file_nodes = set(second_file_nodes) - set(fist_file_nodes)
                if additional_first_file_nodes:
                    checks_passed = False
                    error_msg += 'File %s has additional nodes: %s\n' % (first_file, ', '.join(additional_first_file_nodes))
                if additional_second_file_nodes:
                    checks_passed = False
                    error_msg += 'File %s has additional nodes: %s\n' % (second_file, ', '.join(additional_second_file_nodes))
                common_nodes = set(fist_file_nodes) & set(second_file_nodes)
            else:
                missing_first_file_nodes = set(node_names) - set(fist_file_nodes)
                if missing_first_file_nodes:
                    checks_passed = False
                    error_msg += 'File %s is missing nodes: %s\n' % (first_file, ', '.join(missing_first_file_nodes))
                missing_second_file_nodes = set(node_names) - set(second_file_nodes)
                if missing_second_file_nodes:
                    checks_passed = False
                    error_msg += 'File %s is missing nodes: %s\n' % (second_file, ', '.join(missing_second_file_nodes))
                common_nodes = (set(fist_file_nodes) & set(second_file_nodes)) & set(node_names)
            for node_name in common_nodes:  # loop over all nodes and compare each node, do not abort if one node is wrong
                nrows = first_h5_file.get_node(first_h5_file.root, node_name).nrows
                index_start = 0
                while index_start < nrows:
                    index_stop = index_start + chunk_size
                    first_file_data = first_h5_file.get_node(first_h5_file.root, node_name).read(index_start, index_stop)
                    second_file_data = second_h5_file.get_node(second_h5_file.root, node_name).read(index_start, index_stop)
                    if exact:
                        try:
                            np.testing.assert_array_equal(first_file_data, second_file_data)
                        except AssertionError as e:
                            checks_passed = False
                            error_msg += node_name
                            if detailed_comparison:
                                error_msg += get_array_differences(first_file_data, second_file_data)
                                error_msg += str(e)
                            error_msg += '\n'
                            break
                    else:
                        if not array_close(first_file_data, second_file_data, rtol, atol):
                            checks_passed = False
                            error_msg += node_name
                            if detailed_comparison:
                                error_msg += get_array_differences(first_file_data, second_file_data)
                            error_msg += '\n'
                            break
                    index_start += chunk_size
    return checks_passed, error_msg
