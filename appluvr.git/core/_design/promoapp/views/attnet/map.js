    function (doc) {
        if (doc.doc_type == 'promoapp' && doc.carousel == 'ATT.Net') emit(doc.pkg, doc.interests);
    }
