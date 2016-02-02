    function (doc) {
        if (doc.doc_type == 'interest') emit(doc._id, doc);
    }
