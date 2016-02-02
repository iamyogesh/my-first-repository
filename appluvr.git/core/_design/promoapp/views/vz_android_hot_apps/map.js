function (doc) {
        if (doc.doc_type == 'promoapp' && doc.carousel == 'hot_apps' && doc.platform=='android' && doc.carrier=='Verizon') emit(doc.pkg, [doc.interests,doc.priority]);
    }
