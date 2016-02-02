function (doc) {
if (doc.doc_type == 'user'){
if (!!doc.fb_id)
emit(doc.fb_id, doc.uniq_id);
}
}
