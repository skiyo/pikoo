# Agent capabilities

**English** | [简体中文](agent.zh-CN.md)

The local Agent owns tasks rather than forwarding device events to an application server. Live supplies speech and interaction signals; the independent LLM reasons over bounded classified context and chooses registered tools. Provider responses cannot directly access storage.

| Capability | Device behavior |
|---|---|
| Wake and privacy | Full local wake phrase; no idle audio upload; mute disables capture |
| Conversation | Greeting, follow-up context, interrupt/cancel, 60-second idle timeout and farewell drain |
| Local actions | Shopping/todo lists and explicitly requested memory changes |
| Retrieval | Optional search; source links; extraction only with the corresponding adapter |
| Recovery | Reconnect without old audio replay; USB configuration and snapshot transfer |

Tools declare a name, description and JSON argument schema. Their executor validates arguments and applies bounded operations. Write call IDs and state commit together. Clearing requires confirmation; ambiguous changes should be clarified. A successful saved mutation remains saved if later network work fails. Deduplication covers stored call IDs, not arbitrary semantically equivalent requests with different IDs.

The device is shared, with no speaker identity inference, background automatic memory learning, multi-device synchronization or pre-integrated home automation. Network model access is required for conversation.
