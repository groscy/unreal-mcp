// Copyright unreal-mcp. Source-distributed UE5 editor plugin.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"

class STextBlock;

/** Visible states of the MCP status indicator. */
enum class EMCPStatus : uint8
{
	/** No Python server has connected since the editor started. */
	Disconnected,
	/** A `connected` event arrived but no heartbeat yet — transitional. */
	Connecting,
	/** Heartbeats are arriving within the expected interval. */
	Connected,
	/** Server sent `stopped`, the socket closed, or heartbeats timed out. */
	Stopped,
};

/**
 * Toolbar widget showing the unreal-mcp server connection status as a colored
 * text label with a per-state tooltip. Owns a 1 Hz timeout check that flips the
 * display to Stopped if heartbeats stop arriving.
 */
class SMCPStatusWidget : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SMCPStatusWidget)
		: _HeartbeatTimeoutSeconds(15.0f)
	{}
		/** Seconds without a heartbeat before the widget falls back to Stopped. */
		SLATE_ARGUMENT(float, HeartbeatTimeoutSeconds)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	virtual ~SMCPStatusWidget() override;

	/** Set the displayed state directly (clears any port-in-use override). */
	void SetStatus(EMCPStatus NewStatus);

	/** Record the connecting server's PID and move to the Connecting state. */
	void HandleConnected(int32 Pid);

	/** Register a heartbeat: reset the timeout clock and promote to Connected. */
	void NotifyHeartbeat();

	/** Show a "port in use" message (listener could not bind). */
	void MarkPortInUse();

private:
	/** 1 Hz tick that enforces the heartbeat timeout. */
	bool OnTimeoutTick(float DeltaTime);

	/** Refresh the text label and color from the current state. */
	void RefreshAppearance();

	FText GetLabelText() const;
	FSlateColor GetLabelColor() const;
	FText GetTooltipText() const;

	TSharedPtr<STextBlock> TextBlock;

	EMCPStatus Status = EMCPStatus::Disconnected;
	int32 LastPid = 0;
	bool bPortInUse = false;

	/** Seconds since editor start of the most recent heartbeat (0 = none yet). */
	double LastHeartbeatTime = 0.0;
	float TimeoutSeconds = 15.0f;

	FTSTicker::FDelegateHandle TickerHandle;
};
