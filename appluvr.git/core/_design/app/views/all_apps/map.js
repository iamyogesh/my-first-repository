    function (doc) {
        if (doc.doc_type == 'app') emit(doc._id, doc);
    }
