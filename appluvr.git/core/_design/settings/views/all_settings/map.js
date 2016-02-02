   function (doc) {
        if (doc.doc_type == 'settings') emit(doc._id, doc);
    }
