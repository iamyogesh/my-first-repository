"""
Initial test framework for worker tasks
"""
import unittest
import os
import simplejson as json
from build_card_views import fetch_app_card, fetch_friend_card
import pycallgraph


server = os.environ.get('appluvr_server','http://joohoo.herokuapp.com/v2/')
auth_pwd = os.environ.get('appluvr_pwd','aspirin')


output1=open('test_output/phils_output').read()
out=json.loads(output1)
app_card_output1=json.dumps(out)


output2=open('test_output/marty_output').read()
out=json.loads(output2)
app_card_output2=json.dumps(out)

output3=open('test_output/stephen_output').read()
out=json.loads(output3)
app_card_output3=json.dumps(out)

output4=open('test_output/brad_output').read()
out=json.loads(output4)
app_card_output4=json.dumps(out)

output5=open('test_output/andrew_output').read()
out=json.loads(output5)
app_card_output5=json.dumps(out)

output6=open('test_output/caitlin_output').read()
out=json.loads(output6)
app_card_output6=json.dumps(out)

output7=open('test_output/shara_output').read()
out=json.loads(output7)
app_card_output7=json.dumps(out)

output8=open('test_output/phils_friendcard_output').read()
out=json.loads(output8)
friend_card_output1=json.dumps(out)

output9=open('test_output/marty_friendcard_output').read()
out=json.loads(output9)
friend_card_output2=json.dumps(out)

output10=open('test_output/stephen_friendcard_output').read()
out=json.loads(output10)
friend_card_output3=json.dumps(out)

output11=open('test_output/brad_friendcard_output').read()
out=json.loads(output11)
friend_card_output4=json.dumps(out)

output12=open('test_output/andrew_friendcard_output').read()
out=json.loads(output12)
friend_card_output5=json.dumps(out)

output13=open('test_output/caitlin_friendcard_output').read()
out=json.loads(output13)
friend_card_output6=json.dumps(out)

output14=open('test_output/shara_friendcard_output').read()
out=json.loads(output14)
friend_card_output7=json.dumps(out)


"""
List of all test users & their devices
"""
test_users = [('phil_jxilzpn_hornshaw@tfbnw.net','212361089207890','com.weather.Weather','phil_jxilzpn_hornshaw@tfbnw.net'),
('marty_ixouocm_gabel@tfbnw.net','892032101234567','com.weather.Weather','phil_jxilzpn_hornshaw@tfbnw.net'), ('stephen_yjlmdhf_danos@tfbnw.net','892032101267890','com.weather.Weather','phil_jxilzpn_hornshaw@tfbnw.net'), ('brad_pttszvc_spirrison@tfbnw.net','321089201267890','com.weather.Weather','phil_jxilzpn_hornshaw@tfbnw.net'),   ('andrew_zobydvq_koziara@tfbnw.net','210892012367890','com.weather.Weather','phil_jxilzpn_hornshaw@tfbnw.net'),   ('caitlin_qandmcj_foyt@tfbnw.net','920121082367890','com.weather.Weather','phil_jxilzpn_hornshaw@tfbnw.net'), ('shara_ojwomnc_karasic@tfbnw.net','012321089267890','com.weather.Weather','phil_jxilzpn_hornshaw@tfbnw.net')  
    ]
    
"""
List of expected output for each test function for each user/device combination
"""
test_fetch_app_card_output = { 
('phil_jxilzpn_hornshaw@tfbnw.net','212361089207890','com.weather.Weather'):app_card_output1,('marty_ixouocm_gabel@tfbnw.net','892032101234567','com.weather.Weather'):app_card_output2, ('stephen_yjlmdhf_danos@tfbnw.net','892032101267890','com.weather.Weather'):app_card_output3, ('brad_pttszvc_spirrison@tfbnw.net','321089201267890','com.weather.Weather'):app_card_output4, ('andrew_zobydvq_koziara@tfbnw.net','210892012367890','com.weather.Weather'):app_card_output5,    ('caitlin_qandmcj_foyt@tfbnw.net','920121082367890','com.weather.Weather'):app_card_output6,   ('shara_ojwomnc_karasic@tfbnw.net','012321089267890','com.weather.Weather'):app_card_output7
       }
       
test_fetch_friend_card_output ={
('phil_jxilzpn_hornshaw@tfbnw.net','212361089207890','phil_jxilzpn_hornshaw@tfbnw.net'):friend_card_output1,('marty_ixouocm_gabel@tfbnw.net','892032101234567','phil_jxilzpn_hornshaw@tfbnw.net'):friend_card_output2,('stephen_yjlmdhf_danos@tfbnw.net','892032101267890','phil_jxilzpn_hornshaw@tfbnw.net'):friend_card_output3,('brad_pttszvc_spirrison@tfbnw.net','321089201267890','phil_jxilzpn_hornshaw@tfbnw.net'):friend_card_output4, ('andrew_zobydvq_koziara@tfbnw.net','210892012367890','phil_jxilzpn_hornshaw@tfbnw.net'):friend_card_output5,    ('caitlin_qandmcj_foyt@tfbnw.net','920121082367890','phil_jxilzpn_hornshaw@tfbnw.net'):friend_card_output6,('shara_ojwomnc_karasic@tfbnw.net','012321089267890','phil_jxilzpn_hornshaw@tfbnw.net'):friend_card_output7
      }       

class TestCase(unittest.TestCase):
    
    def setUp(self):
        pass 
    
    def test_fetch_app_card(self):
        for user,device,pkg,friend in test_users:
            filter_func = pycallgraph.GlobbingFilter(include=['build_card_views.fetch_app_card','build_card_views.apps_details','build_card_views.app_friends','build_card_views.friends_comments','build_card_views.user_profile','build_card_views.profile_picture'])
            pycallgraph.start_trace(filter_func=filter_func)
            output = fetch_app_card(server, user, device, pkg, auth_pwd=auth_pwd, debug=False)
            outp=json.loads(output)
            result=json.dumps(outp)
            file_name= user+'_app_card.png'
            pycallgraph.make_dot_graph(file_name)           
            expected_output = test_fetch_app_card_output.get((user,device,pkg), None)
            assert(result == expected_output)
            
                       
        for user,device, pkg,friend in test_users:
            filter_func = pycallgraph.GlobbingFilter(include=['build_card_views.fetch_friend_card','build_card_views.get_rating_of_apps','build_card_views.get_all_my_apps','build_card_views.get_profile_pic','build_card_views.get_user_data','build_card_views.ddb_details', 'build_card_views.get_user_comments','build_card_views.get_common_apps'])
            oup =fetch_friend_card(server, user, device,friend, auth_pwd=auth_pwd,debug=False)
            outp1=json.loads(oup)
            result1=json.dumps(outp1)
            file_name= user+'_friend_card.png'
            pycallgraph.make_dot_graph(file_name)
            expected_output1 = test_fetch_friend_card_output.get((user,device,friend), None)
            assert(result1 == expected_output1)
            
                   
    def tearDown(self):
        pass
    
    
if __name__ == '__main__':
    unittest.main()
    
    
    
    
    
