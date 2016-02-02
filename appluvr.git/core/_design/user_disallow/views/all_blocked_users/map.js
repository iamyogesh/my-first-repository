    function (doc) {
        if (doc.doc_type == 'user_disallow') emit(doc.me, doc);
    }
