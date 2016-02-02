function (doc) {
        if (doc.doc_type == 'device' && (doc.ATT_subid!='' && doc.ATT_subid!=null)) emit(doc.ATT_subid, doc);
    }