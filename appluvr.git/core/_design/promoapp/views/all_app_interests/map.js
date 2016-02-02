    function (doc) {
        if (doc.doc_type == 'promoapp') emit(doc.pkg, doc.interests);
    }
