    function (doc) {
        if (doc.doc_type == 'promoapp' && doc.carousel == 'MyATT') emit(doc.pkg, doc.interests);
    }
