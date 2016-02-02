    function (doc) {
        if (doc.doc_type == 'device') emit(doc._id, doc);
    }
