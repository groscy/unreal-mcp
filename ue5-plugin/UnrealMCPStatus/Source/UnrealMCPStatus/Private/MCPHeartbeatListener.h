// Copyright unreal-mcp. Source-distributed UE5 editor plugin.

#pragma once

#include "CoreMinimal.h"
#include "HAL/Runnable.h"

class FRunnableThread;
class FSocket;

/**
 * Fires when a heartbeat event is received from the Python MCP server.
 * Always invoked on the game thread so listeners can safely touch Slate.
 *
 * @param EventType  one of "connected", "heartbeat", "stopped", or "closed"
 *                   ("closed" is synthesised when the TCP socket drops).
 * @param Pid        the Python process id from a "connected" event, else 0.
 */
DECLARE_DELEGATE_TwoParams(FOnMCPEventReceived, const FString& /*EventType*/, int32 /*Pid*/);

/**
 * A single-client TCP listener that receives newline-delimited JSON heartbeat
 * messages from the Python MCP server. Runs its accept/read loop on a background
 * thread; raised events are marshalled to the game thread.
 *
 * Independent of the Remote Execution protocol — its own socket, own thread.
 */
class FMCPHeartbeatListener : public FRunnable
{
public:
	FMCPHeartbeatListener();
	virtual ~FMCPHeartbeatListener();

	/** Bind and start listening on localhost:Port. Returns false if the bind failed. */
	bool Start(int32 Port);

	/** Stop listening and join the background thread. Safe to call multiple times. */
	void Shutdown();

	/** Delegate fired (on the game thread) for each received event. */
	FOnMCPEventReceived OnEventReceived;

	//~ Begin FRunnable
	virtual uint32 Run() override;
	virtual void Stop() override { bStopRequested = true; }
	//~ End FRunnable

	/** Dispatch an event onto the game thread. */
	void DispatchEvent(const FString& EventType, int32 Pid);

	/** Parse one newline-delimited JSON line and dispatch it. */
	void HandleLine(const FString& Line);

	/** Read from an accepted client until it closes or a stop is requested. */
	void ServiceConnection(FSocket* Client);

	FSocket* ListenSocket = nullptr;
	FRunnableThread* Thread = nullptr;
	FThreadSafeBool bStopRequested = false;
	int32 BoundPort = 0;
};
