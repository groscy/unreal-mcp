// Copyright unreal-mcp. Source-distributed UE5 editor plugin.

#include "SMCPStatusWidget.h"

#include "Widgets/Text/STextBlock.h"

#define LOCTEXT_NAMESPACE "UnrealMCPStatus"

namespace
{
	const FLinearColor ColorDisconnected(0.5f, 0.5f, 0.5f, 1.0f); // grey
	const FLinearColor ColorConnecting(1.0f, 0.8f, 0.0f, 1.0f);   // yellow/amber
	const FLinearColor ColorConnected(0.2f, 0.85f, 0.2f, 1.0f);   // green
	const FLinearColor ColorStopped(0.9f, 0.15f, 0.15f, 1.0f);    // red
}

void SMCPStatusWidget::Construct(const FArguments& InArgs)
{
	TimeoutSeconds = InArgs._HeartbeatTimeoutSeconds;

	ChildSlot
	[
		SAssignNew(TextBlock, STextBlock)
		.Text(this, &SMCPStatusWidget::GetLabelText)
		.ColorAndOpacity(this, &SMCPStatusWidget::GetLabelColor)
		.ToolTipText(this, &SMCPStatusWidget::GetTooltipText)
	];

	// 1 Hz timeout check.
	TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateSP(this, &SMCPStatusWidget::OnTimeoutTick), 1.0f);
}

SMCPStatusWidget::~SMCPStatusWidget()
{
	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}
}

void SMCPStatusWidget::SetStatus(EMCPStatus NewStatus)
{
	bPortInUse = false;
	Status = NewStatus;
	if (NewStatus == EMCPStatus::Connecting || NewStatus == EMCPStatus::Connected)
	{
		LastHeartbeatTime = FPlatformTime::Seconds();
	}
	RefreshAppearance();
}

void SMCPStatusWidget::HandleConnected(int32 Pid)
{
	LastPid = Pid;
	LastHeartbeatTime = FPlatformTime::Seconds();
	SetStatus(EMCPStatus::Connecting);
}

void SMCPStatusWidget::NotifyHeartbeat()
{
	LastHeartbeatTime = FPlatformTime::Seconds();
	// First heartbeat after `connected` promotes us to the steady Connected state.
	if (Status == EMCPStatus::Connecting || Status == EMCPStatus::Stopped)
	{
		Status = EMCPStatus::Connected;
		bPortInUse = false;
		RefreshAppearance();
	}
}

void SMCPStatusWidget::MarkPortInUse()
{
	bPortInUse = true;
	RefreshAppearance();
}

bool SMCPStatusWidget::OnTimeoutTick(float /*DeltaTime*/)
{
	if ((Status == EMCPStatus::Connected || Status == EMCPStatus::Connecting)
		&& LastHeartbeatTime > 0.0)
	{
		const double Elapsed = FPlatformTime::Seconds() - LastHeartbeatTime;
		if (Elapsed > TimeoutSeconds)
		{
			Status = EMCPStatus::Stopped;
			RefreshAppearance();
		}
	}
	return true; // keep ticking
}

void SMCPStatusWidget::RefreshAppearance()
{
	if (TextBlock.IsValid())
	{
		TextBlock->SetText(GetLabelText());
		TextBlock->SetColorAndOpacity(GetLabelColor());
		TextBlock->SetToolTipText(GetTooltipText());
	}
}

FText SMCPStatusWidget::GetLabelText() const
{
	if (bPortInUse)
	{
		return LOCTEXT("StatusPortInUse", "MCP: Port in use");
	}
	switch (Status)
	{
	case EMCPStatus::Connecting:
		return LOCTEXT("StatusConnecting", "MCP: Connecting");
	case EMCPStatus::Connected:
		return LOCTEXT("StatusConnected", "MCP: Connected");
	case EMCPStatus::Stopped:
		return LOCTEXT("StatusStopped", "MCP: Stopped");
	case EMCPStatus::Disconnected:
	default:
		return LOCTEXT("StatusDisconnected", "MCP: Disconnected");
	}
}

FSlateColor SMCPStatusWidget::GetLabelColor() const
{
	if (bPortInUse)
	{
		return FSlateColor(ColorStopped);
	}
	switch (Status)
	{
	case EMCPStatus::Connecting:
		return FSlateColor(ColorConnecting);
	case EMCPStatus::Connected:
		return FSlateColor(ColorConnected);
	case EMCPStatus::Stopped:
		return FSlateColor(ColorStopped);
	case EMCPStatus::Disconnected:
	default:
		return FSlateColor(ColorDisconnected);
	}
}

FText SMCPStatusWidget::GetTooltipText() const
{
	if (bPortInUse)
	{
		return LOCTEXT("TooltipPortInUse",
			"MCP heartbeat port is already in use. Status updates are disabled for this editor session.");
	}
	switch (Status)
	{
	case EMCPStatus::Connecting:
		return LOCTEXT("TooltipConnecting", "MCP server is connecting...");
	case EMCPStatus::Connected:
		return FText::Format(
			LOCTEXT("TooltipConnected", "MCP server is connected (PID: {0})"),
			FText::AsNumber(LastPid, &FNumberFormattingOptions::DefaultNoGrouping()));
	case EMCPStatus::Stopped:
		return LOCTEXT("TooltipStopped", "MCP server has stopped or is unreachable. Restart your MCP client.");
	case EMCPStatus::Disconnected:
	default:
		return LOCTEXT("TooltipDisconnected",
			"MCP server has not connected. Start the MCP server via your MCP client configuration.");
	}
}

#undef LOCTEXT_NAMESPACE
