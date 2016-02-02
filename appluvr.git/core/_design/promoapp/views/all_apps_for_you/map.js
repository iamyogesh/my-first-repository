    function (doc) {
        if (doc.doc_type == 'promoapp' && doc.carousel == 'apps_for_you') emit(doc.pkg, doc.interests);
    }
