from collections import defaultdict
def merge_lists(list1, list2, list3):     
    d = defaultdict(dict)
    for final_list in (list1, list2, list3):
        for elem in final_list:
            d[elem['uniq_id']].update(elem)
    return_list=  d.values()
    return return_list
