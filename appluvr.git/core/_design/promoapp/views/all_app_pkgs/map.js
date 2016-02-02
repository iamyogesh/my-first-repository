    function (doc) {
        if (doc.doc_type == 'promoapp') emit(doc._id, null);
    }
