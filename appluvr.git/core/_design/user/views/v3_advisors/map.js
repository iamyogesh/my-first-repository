function (doc) {
        if (doc.doc_type == 'user')  
         if ((doc.advisor_carrier && doc.advisor_carrier!='')&&(!!doc.advisor && (doc.advisor.toLowerCase() == 'verizon' || doc.advisor.toLowerCase() == 'appolicious' || doc.advisor.toLowerCase() == 'att' || doc.advisor.toLowerCase() == 'bm')))
             emit(doc._id, doc);
    }