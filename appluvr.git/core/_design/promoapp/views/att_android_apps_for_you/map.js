 function (doc) {
        if (doc.doc_type == 'promoapp' && doc.carousel == 'apps_for_you' && doc.platform=='android' && doc.carrier=='ATT') emit(doc.pkg, [doc.interests,doc.priority]);
    }
