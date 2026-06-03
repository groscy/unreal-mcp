// Copyright unreal-mcp. Source-distributed UE5 editor plugin.

#include "UnrealMCPStatusModule.h"

#include "MCPHeartbeatListener.h"
#include "SMCPStatusWidget.h"
#include "ToolMenus.h"
#include "Widgets/Layout/SBox.h"

#define LOCTEXT_NAMESPACE "UnrealMCPStatus"

DEFINE_LOG_CATEGORY_STATIC(LogMCPStatusModule, Log, All);

static TAutoConsoleVariable<int32> CVarHeartbeatPort(
	TEXT("mcp.HeartbeatPort"),
	6690,
	TEXT("TCP port the UnrealMCPStatus plugin listens on for MCP server heartbeats."),
	ECVF_Default);

static TAutoConsoleVariable<int32> CVarHeartbeatIntervalSeconds(
	TEXT("mcp.HeartbeatIntervalSeconds"),
	5,
	TEXT("Expected interval between MCP server heartbeats, in seconds."),
	ECVF_Default);

static TAutoConsoleVariable<int32> CVarHeartbeatTimeoutBeats(
	TEXT("mcp.HeartbeatTimeoutBeats"),
	3,
	TEXT("Missed heartbeats before the status widget falls back to Stopped."),
	ECVF_Default);

static const FName ToolbarMenuName(TEXT("LevelEditor.LevelEditorToolBar.PlayToolBar"));
static const FName ToolbarSectionName(TEXT("UnrealMCPStatus"));
static const FName ToolbarEntryName(TEXT("MCPStatusWidget"));

void FUnrealMCPStatusModule::StartupModule()
{
	const int32 IntervalSeconds = FMath::Max(1, CVarHeartbeatIntervalSeconds.GetValueOnGameThread());
	const int32 TimeoutBeats = FMath::Max(1, CVarHeartbeatTimeoutBeats.GetValueOnGameThread());
	const float TimeoutSeconds = static_cast<float>(IntervalSeconds * TimeoutBeats);

	StatusWidget = SNew(SMCPStatusWidget).HeartbeatTimeoutSeconds(TimeoutSeconds);

	// Start the heartbeat listener and route its events to the widget.
	Listener = MakeShared<FMCPHeartbeatListener>();
	Listener->OnEventReceived.BindRaw(this, &FUnrealMCPStatusModule::HandleHeartbeatEvent);

	const int32 Port = CVarHeartbeatPort.GetValueOnGameThread();
	if (!Listener->Start(Port))
	{
		// Bind failed (port in use) — keep the widget but flag it.
		if (StatusWidget.IsValid())
		{
			StatusWidget->MarkPortInUse();
		}
	}

	// UToolMenus may not be ready yet at PostEngineInit; defer if necessary.
	if (UToolMenus::IsToolMenuUIEnabled())
	{
		RegisterToolbarWidget();
	}
	else
	{
		UToolMenus::RegisterStartupCallback(FSimpleMulticastDelegate::FDelegate::CreateRaw(
			this, &FUnrealMCPStatusModule::RegisterToolbarWidget));
	}
}

void FUnrealMCPStatusModule::ShutdownModule()
{
	UToolMenus::UnRegisterStartupCallback(this);

	if (bToolbarRegistered && UToolMenus::IsToolMenuUIEnabled())
	{
		if (UToolMenu* Menu = UToolMenus::Get()->ExtendMenu(ToolbarMenuName))
		{
			Menu->RemoveSection(ToolbarSectionName);
		}
		UToolMenus::Get()->RefreshAllWidgets();
		bToolbarRegistered = false;
	}

	if (Listener.IsValid())
	{
		Listener->OnEventReceived.Unbind();
		Listener->Shutdown();
		Listener.Reset();
	}

	StatusWidget.Reset();
}

void FUnrealMCPStatusModule::RegisterToolbarWidget()
{
	if (bToolbarRegistered || !StatusWidget.IsValid())
	{
		return;
	}

	UToolMenus* ToolMenus = UToolMenus::Get();
	if (ToolMenus == nullptr)
	{
		return;
	}

	UToolMenu* Toolbar = ToolMenus->ExtendMenu(ToolbarMenuName);
	if (Toolbar == nullptr)
	{
		return;
	}

	FToolMenuSection& Section = Toolbar->FindOrAddSection(ToolbarSectionName);
	Section.AddEntry(FToolMenuEntry::InitWidget(
		ToolbarEntryName,
		SNew(SBox)
		.VAlign(VAlign_Center)
		.Padding(FMargin(8.0f, 0.0f))
		[
			StatusWidget.ToSharedRef()
		],
		FText::GetEmpty(),
		/*bNoIndent=*/ true,
		/*bSearchable=*/ false));

	ToolMenus->RefreshAllWidgets();
	bToolbarRegistered = true;

	UE_LOG(LogMCPStatusModule, Log, TEXT("unreal-mcp: registered status widget in level editor toolbar"));
}

void FUnrealMCPStatusModule::HandleHeartbeatEvent(const FString& EventType, int32 Pid)
{
	// Delegate is already marshalled to the game thread by the listener.
	if (!StatusWidget.IsValid())
	{
		return;
	}

	if (EventType == TEXT("connected"))
	{
		StatusWidget->HandleConnected(Pid);
	}
	else if (EventType == TEXT("heartbeat"))
	{
		StatusWidget->NotifyHeartbeat();
	}
	else if (EventType == TEXT("stopped") || EventType == TEXT("closed"))
	{
		StatusWidget->SetStatus(EMCPStatus::Stopped);
	}
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FUnrealMCPStatusModule, UnrealMCPStatus)
