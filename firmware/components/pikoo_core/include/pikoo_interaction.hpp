#pragma once
#include <cstdint>
#include <string>

namespace pikoo {
// Deliberately match whole final user utterances. Mentions, questions and
// negations containing "再见" must never terminate a conversation.
inline bool is_farewell(const std::string &text) {
  std::string normalized;
  const std::string punctuation = "，。！？、；：～·“”‘’";
  for (size_t i=0;i<text.size();) {
    unsigned char c=text[i];
    size_t n=c<0x80?1:(c<0xe0?2:(c<0xf0?3:4));
    if(i+n>text.size())return false;
    auto part=text.substr(i,n);i+=n;
    if(n==1&&(c<=32||std::string(",.!?;:~\"'").find(char(c))!=std::string::npos))continue;
    if(n>1&&punctuation.find(part)!=std::string::npos)continue;
    if(n==1&&c>='A'&&c<='Z')part[0]=char(c-'A'+'a');
    normalized+=part;
  }
  for(const char *phrase:{"再见","拜拜","拜","皮酷再见","再见皮酷","皮酷拜拜","拜拜皮酷",
       "好了再见","好再见","好的再见","谢谢再见","谢谢你再见","那再见","我们下次再聊",
       "下次再聊","结束对话","结束通话","不聊了","晚安","皮酷晚安","晚安皮酷",
       "pikoo再见","再见pikoo","pikoo拜拜","拜拜pikoo","pikoo晚安","晚安pikoo",
       "goodbye","byebye","goodbyepikoo","pikoogoodbye","byepikoo","pikoobye"})
    if(normalized==phrase)return true;
  return false;
}

// Owned exclusively by the session task; independent of transport and hardware.
class Interaction {
 public:
  void wake() { reset(); greeting_pending_=true; }
  void reset() { greeting_pending_=false;closing_=false;finished_=false;deadline_=0;turn_.clear();response_.clear();latest_turn_.clear();latest_response_.clear();latest_finished_=false; }
  bool greeting_pending() const { return greeting_pending_; }
  void greeting_sent() { greeting_pending_=false; }
  bool transcript(const std::string &role,bool final,const std::string &text,
                  const std::string &turn,uint64_t now) {
    if(closing_||role!="user"||!final||!is_farewell(text))return false;
    closing_=true;greeting_pending_=false;turn_=turn;deadline_=now+20000;
    // A provider may announce and even finish the response before final ASR.
    if(!turn.empty()&&latest_turn_==turn){response_=latest_response_;finished_=latest_finished_;}
    return true;
  }
  void response(const std::string &turn,const std::string &id) {
    if(id.empty())return;
    if(id!=latest_response_){latest_response_=id;latest_turn_=turn;latest_finished_=false;}
    if(closing_&&(turn_.empty()||turn.empty()||turn_==turn)&&response_.empty())response_=id;
  }
  void drained(const std::string &id) {
    if(id==latest_response_)latest_finished_=true;
    if(closing_&&!id.empty()&&id==response_)finished_=true;
  }
  bool closing() const { return closing_; }
  bool finish_due(uint64_t now,bool playing) const {
    return closing_&&((finished_&&!playing)||now>=deadline_);
  }
 private:
  bool greeting_pending_=false,closing_=false,finished_=false,latest_finished_=false;
  uint64_t deadline_=0;
  std::string turn_,response_,latest_turn_,latest_response_;
};
} // namespace pikoo
