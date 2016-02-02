"""

Initial test framework for worker tasks

"""
import unittest
import os
import simplejson as json

from build_carousel_views import fetch_my_friends, fetch_mfa, fetch_recos, fetch_my_apps
server = os.environ.get('appluvr_server','http://baadaami.herokuapp.com/v2/')
auth_pwd = os.environ.get('appluvr_pwd','aspirin')

"""
List of all test users & their devices
"""
test_users = [
    ('andrew_zobydvq_koziara@tfbnw.net', '210892012367890'),
    ('brad_pttszvc_spirrison@tfbnw.net', '321089201267890'),
    ('caitlin_qandmcj_foyt@tfbnw.net','920121082367890'),
    ('marty_ixouocm_gabel@tfbnw.net', '892032101234567'),
    ('phil_jxilzpn_hornshaw@tfbnw.net','212361089207890'),
    ('stephen_yjlmdhf_danos@tfbnw.net', '892032101267890'),
    ('shara_ojwomnc_karasic@tfbnw.net', '012321089267890')
    ]

mf_output = { 
    ('andrew_zobydvq_koziara@tfbnw.net', '210892012367890') : 'test_output/mf_andrew',
    ('brad_pttszvc_spirrison@tfbnw.net', '321089201267890') : 'test_output/mf_brad',
    ('caitlin_qandmcj_foyt@tfbnw.net','920121082367890') : 'test_output/mf_caitlin',
    ('marty_ixouocm_gabel@tfbnw.net', '892032101234567') : 'test_output/mf_marty',
    ('phil_jxilzpn_hornshaw@tfbnw.net','212361089207890') : 'test_output/mf_phil',
    ('stephen_yjlmdhf_danos@tfbnw.net', '892032101267890') : 'test_output/mf_stephen',
    ('shara_ojwomnc_karasic@tfbnw.net', '012321089267890') : 'test_output/mf_shara'
    }


mfa_output = { 
    ('andrew_zobydvq_koziara@tfbnw.net', '210892012367890') : 'test_output/mfa_andrew',
    ('brad_pttszvc_spirrison@tfbnw.net', '321089201267890') : 'test_output/mfa_brad',
    ('caitlin_qandmcj_foyt@tfbnw.net','920121082367890') : 'test_output/mfa_caitlin',
    ('marty_ixouocm_gabel@tfbnw.net', '892032101234567') : 'test_output/mfa_marty',
    ('phil_jxilzpn_hornshaw@tfbnw.net','212361089207890') : 'test_output/mfa_phil',
    ('stephen_yjlmdhf_danos@tfbnw.net', '892032101267890') : 'test_output/mfa_stephen',
    ('shara_ojwomnc_karasic@tfbnw.net', '012321089267890') : 'test_output/mfa_shara'
    }

recos_afy_output = { 
    ('andrew_zobydvq_koziara@tfbnw.net', '210892012367890') : 'test_output/afy_andrew',
    ('brad_pttszvc_spirrison@tfbnw.net', '321089201267890') : 'test_output/afy_brad',
    ('caitlin_qandmcj_foyt@tfbnw.net','920121082367890') : 'test_output/afy_caitlin',
    ('marty_ixouocm_gabel@tfbnw.net', '892032101234567') : 'test_output/afy_marty',
    ('phil_jxilzpn_hornshaw@tfbnw.net','212361089207890') : 'test_output/afy_phil',
    ('stephen_yjlmdhf_danos@tfbnw.net', '892032101267890') : 'test_output/afy_stephen',
    ('shara_ojwomnc_karasic@tfbnw.net', '012321089267890') : 'test_output/afy_shara'
    }

recos_ha_output = { 
    ('andrew_zobydvq_koziara@tfbnw.net', '210892012367890') : 'test_output/ha_andrew',
    ('brad_pttszvc_spirrison@tfbnw.net', '321089201267890') : 'test_output/ha_brad',
    ('caitlin_qandmcj_foyt@tfbnw.net','920121082367890') : 'test_output/ha_caitlin',
    ('marty_ixouocm_gabel@tfbnw.net', '892032101234567') : 'test_output/ha_marty',
    ('phil_jxilzpn_hornshaw@tfbnw.net','212361089207890') : 'test_output/ha_phil',
    ('stephen_yjlmdhf_danos@tfbnw.net', '892032101267890') : 'test_output/ha_stephen',
    ('shara_ojwomnc_karasic@tfbnw.net', '012321089267890') : 'test_output/ha_shara'
    }

my_apps_output = { 
    ('andrew_zobydvq_koziara@tfbnw.net', '210892012367890') : 'test_output/my_apps_andrew',
    ('brad_pttszvc_spirrison@tfbnw.net', '321089201267890') : 'test_output/my_apps_brad',
    ('caitlin_qandmcj_foyt@tfbnw.net','920121082367890') : 'test_output/my_apps_caitlin',
    ('marty_ixouocm_gabel@tfbnw.net', '892032101234567') : 'test_output/my_apps_marty',
    ('phil_jxilzpn_hornshaw@tfbnw.net','212361089207890') : 'test_output/my_apps_phil',
    ('stephen_yjlmdhf_danos@tfbnw.net', '892032101267890') : 'test_output/my_apps_stephen',
    ('shara_ojwomnc_karasic@tfbnw.net', '012321089267890') : 'test_output/my_apps_shara'
    }

class TestCase(unittest.TestCase):
    
    def setUp(self):
        pass 

    def test_fetch_my_friends(self):
        for user,device in test_users:
            result1 = fetch_my_friends(server, user, device, auth_pwd=auth_pwd, debug=False)
            result2=json.loads(result1)
            output=json.dumps(result2)
            result3=open(mf_output.get((user,device), None)).read()
            result4=json.loads(result3)
            expected_output=json.dumps(result4) 
            assert (output==expected_output)
           
    def test_fetch_mfa(self):
        for user,device in test_users:
            result1 = fetch_mfa(server, user, device, auth_pwd=auth_pwd, debug=False)
            result2=json.loads(result1)
            output=json.dumps(result2)
            result3 = open(mfa_output.get((user,device), None)).read()
            result4=json.loads(result3)
            expected_output=json.dumps(result4)
            assert(output==expected_output)
           

    def test_fetch_recos(self):
        """
       Since recommendations will keep changing, test against valid data, and count
        
        """
        for user,device in test_users:
	        res1 = fetch_recos('apps_for_you',server, user, device, auth_pwd=auth_pwd, debug=False)
	        res2=json.loads(res1)
	        res3 = open(recos_afy_output.get((user,device), None)).read()
	        expected_output1=json.loads(res3)
	        assert(res2['count'] == expected_output1['count'])
	        

        for user,device in test_users:
	        res5 = fetch_recos('hot_apps', server, user, device, auth_pwd=auth_pwd, debug=False)
	        res6=json.loads(res5)
	        res7 = open(recos_ha_output.get((user,device), None)).read()
	        expected_output2=json.loads(res7)
	        assert(res6['count']==expected_output2['count']) 
   

    def test_fetch_my_apps(self):
 	    for user,device in test_users:
	        result1 = fetch_my_apps(server, user, device, auth_pwd=auth_pwd, debug=False)
	        result2=json.loads(result1)
	        output=json.dumps(result2)
	        result3 = open(my_apps_output.get((user,device), None)).read()
	        result4=json.loads(result3)
	        expected_output=json.dumps(result4)    
	        assert(output==expected_output)
     

    def tearDown(self):
        pass    
    
if __name__ == '__main__':
    unittest.main()
