    function (doc) {
        if (doc.doc_type == 'promoapp' && doc.carousel == 'hot_apps') emit(doc.pkg, doc.interests);
    }
