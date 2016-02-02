function (doc) {
        if (doc.doc_type == 'user' && doc.email != null) emit(doc._id, doc);
    }