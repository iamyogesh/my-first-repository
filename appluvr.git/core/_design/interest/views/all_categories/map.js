    function (doc) {
        if (doc.doc_type == 'interest') emit(doc.categories, null);
    }
