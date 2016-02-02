function (doc) {
        if (doc.doc_type == 'promoapp' && doc.carousel == 'hot_apps' && doc.platform=='ios' && doc.carrier=='ATT') emit(doc.pkg, [doc.interests,doc.priority]);
    }
