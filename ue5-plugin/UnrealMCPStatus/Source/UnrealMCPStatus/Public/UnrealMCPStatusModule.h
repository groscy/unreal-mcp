// Copyright unreal-mcp. Source-distributed UE5 editor plugin.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleInterface.h"

class FMCPHeartbeatListener;
class SMCPStatusWidget;

/**
 * Editor module for the unreal-mcp status indicator.
 *
 * On startup it opens a TCP heartbeat listener (default port 6690) and registers
 * a Slate status widget in the level editor toolbar. Heartbeat events received
 * from the Python MCP server drive the widget's displayed state.
 */
class FUnrealMCPStatusModule : public IModuleInterface
{
public:
	//~ Begin IModuleInterface
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
	//~ End IModuleInterface

private:
	/** Register the status widget into the level editor toolbar (via UToolMenus). */
	void RegisterToolbarWidget();

	/** Map a heartbeat event onto the widget. Runs on the game thread. */
	void HandleHeartbeatEvent(const FString& EventType, int32 Pid);

	/** True once the toolbar entry has been registered. */
	bool bToolbarRegistered = false;

	/** Background TCP listener for heartbeat messages from the Python server. */
	TSharedPtr<FMCPHeartbeatListener> Listener;

	/** The toolbar status widget. */
	TSharedPtr<SMCPStatusWidget> StatusWidget;
};
