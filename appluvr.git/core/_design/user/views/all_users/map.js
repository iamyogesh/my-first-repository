    function (doc) {
        if (doc.doc_type == 'user') emit(doc._id, doc);
    }
