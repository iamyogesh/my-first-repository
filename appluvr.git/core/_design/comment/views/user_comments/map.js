function (doc) {
    if (doc.doc_type == 'comment') emit(doc._id.split('+')[0], doc);
}
